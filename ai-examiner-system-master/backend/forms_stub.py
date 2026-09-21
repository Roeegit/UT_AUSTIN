"""
forms_stub.py — Google Forms + Drive submission intake.

The non-GitHub half of submission intake (MULTI_COURSE_MIGRATION §4.3c). Deliberately
mirrors github_stub's public surface so the two are interchangeable behind
submission_source.py, and writes to the SAME GCS layout so everything downstream
(load_local_submission, build_exam_context, the graders) is unchanged:

    {assignment_name}/{student_key}/{filename}

Where GitHub identifies a student by github_username, a Form identifies them by the
9-digit university ID they typed into the form. Both are just "the student key" as far
as storage is concerned.

Per-assignment configuration lives in config.FORM_SOURCES, so adding a course or an
assignment is a dict entry, not code.

Reads: the responses sheet (Sheets API) → a Drive file id per upload → the file itself
(Drive API). Requires drive.readonly in google_apis._SCOPES and the Drive API enabled
on the project.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from config import FORM_SOURCES


# github_stub builds its GCS client at import time, so these are imported lazily —
# same reasoning as database.py's lazy connector: keeps this module importable
# offline (tests, scripts, the routing check) without credentials.

def _bucket():
    from github_stub import _bucket as _gh_bucket
    return _gh_bucket()


def _gcs_path(assignment_name: str, student_key: str, filename: str) -> str:
    """Identical storage layout to the GitHub path — one definition, not two."""
    from github_stub import _gcs_path as _gh_path
    return _gh_path(assignment_name, student_key, filename)


# ---------------------------------------------------------------------------
# Result type — same shape as github_stub.FetchResult so callers don't branch
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    student_key:   str
    source:        str                                   # the sheet id, for the audit trail
    files_saved:   list[str] = field(default_factory=list)
    files_missing: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.files_saved) > 0


class FormConfigError(RuntimeError):
    """The assignment has no Form configuration, or the configuration is unusable."""


# ---------------------------------------------------------------------------
# Google clients
# ---------------------------------------------------------------------------

def _sheets():
    from googleapiclient.discovery import build
    from google_apis import _credentials
    return build("sheets", "v4", credentials=_credentials(), cache_discovery=False)


def _drive():
    from googleapiclient.discovery import build
    from google_apis import _credentials
    return build("drive", "v3", credentials=_credentials(), cache_discovery=False)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def config_for(assignment_name: str) -> dict:
    cfg = FORM_SOURCES.get(assignment_name)
    if not cfg:
        raise FormConfigError(
            f"no FORM_SOURCES entry for '{assignment_name}' — add one in config.py")
    if not cfg.get("sheet_id"):
        raise FormConfigError(f"FORM_SOURCES['{assignment_name}'] has no sheet_id")
    return cfg


def is_form_assignment(assignment_name: str) -> bool:
    return assignment_name in FORM_SOURCES


# ---------------------------------------------------------------------------
# Reading the responses sheet
# ---------------------------------------------------------------------------

_DRIVE_ID_RE = re.compile(r"(?:[?&]id=|/d/|/file/d/)([A-Za-z0-9_-]{20,})")


def _extract_drive_id(cell: str) -> list[str]:
    """A Forms upload cell holds one or more Drive URLs, comma-separated."""
    return _DRIVE_ID_RE.findall(cell or "")


def _normalise_id(raw: str) -> str:
    """Students type IDs with spaces, dashes or a stray leading apostrophe."""
    return re.sub(r"\D", "", raw or "")


def read_rows(assignment_name: str) -> list[dict]:
    """This assignment's response rows as {column_header: value}, oldest first.

    One form per course, not one per assignment: the form carries a dropdown naming the
    assignment, and each FORM_SOURCES entry says which option means it —

        "assignment_column": "מטלה",     the dropdown question's title
        "assignment_value":  "תרגיל 3",  the option that selects this assignment

    Rows for the other assignments are filtered out here, so every caller
    (latest_row_for, list_submitted_ids, the fetch path) is scoped correctly and none of
    them needs to know the form is shared.

    Omit both keys and nothing is filtered — a dedicated one-assignment form still works
    exactly as before.
    """
    cfg = config_for(assignment_name)
    svc = _sheets()
    tab = cfg.get("tab")
    if not tab:
        meta = svc.spreadsheets().get(spreadsheetId=cfg["sheet_id"]).execute()
        tab = meta["sheets"][0]["properties"]["title"]

    values = svc.spreadsheets().values().get(
        spreadsheetId=cfg["sheet_id"], range=f"{tab}!A:Z",
    ).execute().get("values", [])

    if not values:
        return []
    header, *rows = values
    out = [{header[i]: (r[i] if i < len(r) else "") for i in range(len(header))}
           for r in rows]

    col = (cfg.get("assignment_column") or "").strip()
    want = (cfg.get("assignment_value") or "").strip()
    if not col or not want:
        return out

    if header and col not in header:
        # Better to fail loudly than to hand back every assignment's rows: silently
        # unfiltered, a student's hw3 lookup could match their hw7 submission.
        raise FormConfigError(
            f"FORM_SOURCES['{assignment_name}'].assignment_column={col!r} is not a column "
            f"in the responses sheet. Columns: {header}")
    return [r for r in out if (r.get(col) or "").strip() == want]


def latest_row_for(student_key: str, assignment_name: str) -> dict | None:
    """The student's most recent response. Later submissions supersede earlier ones."""
    cfg = config_for(assignment_name)
    id_col = cfg.get("id_column", "ID")
    want = _normalise_id(student_key)
    matches = [r for r in read_rows(assignment_name)
               if _normalise_id(r.get(id_col, "")) == want]
    return matches[-1] if matches else None


def name_for(student_key: str, assignment_name: str) -> str | None:
    """The name the student typed on the form, or None.

    On the GitHub path a name can only come from a roster, because a repo carries nothing but
    a username. A form can simply ask, which is why a Forms course needs no roster at all —
    but only if the form has a name field and FORM_SOURCES names it in `name_column`.

    Returns None when unconfigured or blank, so callers keep whatever the roster gave them.
    """
    cfg = config_for(assignment_name)
    col = (cfg.get("name_column") or "").strip()
    if not col:
        return None
    row = latest_row_for(student_key, assignment_name)
    if not row:
        return None
    return (row.get(col) or "").strip() or None


def list_submitted_ids(assignment_name: str) -> list[str]:
    """Every distinct student key that has submitted — for admin/roster reconciliation."""
    cfg = config_for(assignment_name)
    id_col = cfg.get("id_column", "ID")
    seen, out = set(), []
    for r in read_rows(assignment_name):
        sid = _normalise_id(r.get(id_col, ""))
        if sid and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out


# ---------------------------------------------------------------------------
# Drive download
# ---------------------------------------------------------------------------

def _download(file_id: str) -> tuple[str, str]:
    """Returns (drive_filename, text_content)."""
    from googleapiclient.http import MediaIoBaseDownload
    drive = _drive()
    meta = drive.files().get(fileId=file_id, fields="name,mimeType,size").execute()
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, drive.files().get_media(fileId=file_id))
    done = False
    while not done:
        _, done = dl.next_chunk()
    return meta.get("name", file_id), buf.getvalue().decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Public: fetch + save  (mirrors github_stub.fetch_and_save_submission)
# ---------------------------------------------------------------------------

def fetch_and_save_submission(student_key: str, assignment_name: str) -> FetchResult:
    """
    Locate the student's latest Form response, download each uploaded file, and save
    to GCS at {assignment_name}/{student_key}/{filename}.

    Note the stored filename comes from config, NOT from Drive: Forms appends the
    submitter's display name to every upload ("ex1 - Shachar.md"), so the Drive name
    is neither stable nor safe to key on.
    """
    cfg = config_for(assignment_name)
    result = FetchResult(student_key=_normalise_id(student_key), source=cfg["sheet_id"])

    row = latest_row_for(student_key, assignment_name)
    if row is None:
        print(f"[Forms] no response found for {student_key} in {assignment_name}")
        result.files_missing = list(cfg.get("files", {}).values()) or ["(none)"]
        return result

    bucket = _bucket()
    # {sheet column: filename to store it as}
    files_map: dict[str, str] = cfg.get("files") or {
        cfg.get("file_column", "Transcription"): cfg.get("filename", "submission.md")
    }

    for column, stored_name in files_map.items():
        ids = _extract_drive_id(row.get(column, ""))
        if not ids:
            result.files_missing.append(stored_name)
            print(f"[Forms]   FAIL no upload in column '{column}'")
            continue
        try:
            drive_name, content = _download(ids[0])
        except Exception as exc:
            result.files_missing.append(stored_name)
            print(f"[Forms]   FAIL download failed for '{column}': {exc}")
            continue

        blob = bucket.blob(_gcs_path(assignment_name, result.student_key, stored_name))
        blob.upload_from_string(content, content_type="text/plain; charset=utf-8")
        result.files_saved.append(stored_name)
        print(f"[Forms]   OK   saved  {stored_name}  ({len(content):,} chars, "
              f"from Drive '{drive_name}')")

    return result


# ---------------------------------------------------------------------------
# Public: read back  (mirrors github_stub.load_local_submission)
# ---------------------------------------------------------------------------

def load_local_submission(student_key: str, assignment_name: str) -> dict[str, str]:
    """Read previously fetched files from GCS. Missing → empty string, which
    build_exam_context renders as [NOT SUBMITTED]."""
    cfg = config_for(assignment_name)
    files_map: dict[str, str] = cfg.get("files") or {
        cfg.get("file_column", "Transcription"): cfg.get("filename", "submission.md")
    }
    bucket = _bucket()
    key = _normalise_id(student_key)

    out: dict[str, str] = {}
    for stored_name in files_map.values():
        blob = bucket.blob(_gcs_path(assignment_name, key, stored_name))
        try:
            out[stored_name] = blob.download_as_text(encoding="utf-8").strip()
        except Exception:
            out[stored_name] = ""
    return out


# ---------------------------------------------------------------------------
# Public: does a submission exist  (drives the pre-exam lookup screen)
# ---------------------------------------------------------------------------

def submission_exists(student_key: str, assignment_name: str) -> bool:
    try:
        return latest_row_for(student_key, assignment_name) is not None
    except FormConfigError:
        return False
