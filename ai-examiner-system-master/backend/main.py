"""
main.py — FastAPI backend for the Automated Oral Exam system.

Endpoints:
  POST /api/admin/fetch-submission       — pull one student's files from GitHub Classroom → GCS
  POST /api/auth/start                   — begin an exam session (reads from GCS)
  POST /api/exam/answer                  — submit a student answer, receive next question
  GET  /api/admin/results/{github_username} — professor view: full log + final grade

Typical workflow:
  1. POST /api/admin/fetch-submission      ← professor runs this once per student
  2. POST /api/auth/start                  ← student (or cli_tester) runs this
  3. POST /api/exam/answer  (×3)
  4. GET  /api/admin/results/{github_username}

Run with:
  cd backend
  uvicorn main:app --reload --port 8000
"""

import json
import os
import random
import smtplib
import ssl
import statistics
from collections import Counter
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

_COURSE_FROM_EMAIL  = "os.biu.2026@gmail.com"
_COURSE_FROM_NAME   = "מערכות הפעלה — בר-אילן"
_COURSE_FROM_HEADER = formataddr((_COURSE_FROM_NAME, _COURSE_FROM_EMAIL))
from typing import Optional

from dotenv import load_dotenv
load_dotenv()   # loads backend/.env (or project-root/.env) into os.environ

import re as _re
import anthropic
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from agents import (
    call_code_reviewer,
    call_examiner_q1,
    call_examiner_qn,
    call_grader,
    compute_final_grade,
    serialize_messages,
)
from accommodations import EXTENDED_TIME_SECONDS, is_extended_time
from distress_email_template import DISTRESS_EMAIL_BODY, DISTRESS_EMAIL_SUBJECT
from config import (
    ASSIGN_DIR,
    ASSIGNMENT_FILES,
    ASSIGNMENT_LABELS,
    CODE_REVIEWER_PROMPT_PATH,
    COURSE_ID,
    DEFAULT_ASSIGNMENT,
    EXAMINER_PROMPT_PATH,
    GRADER_PROMPT_PATH,
    KNOWN_ASSIGNMENTS,
    LATEST_ASSIGNMENT,
    MAX_ANSWER_CHARS,
    QA_ASSIGNMENTS,
    STUDENT_FILES,
)
from database import Base, engine, get_db
# Submission intake is routed per assignment (GitHub Classroom vs Google Forms)
# by submission_source; see config.FORM_SOURCES. GitHub remains the default.
from config import (
    student_key_for,
    identity_mode_for,
    course_ui,
    is_unlimited_retake,
    assignment_scope,
)
from submission_source import (
    source_for,
    serves_github,
    student_name,
    build_exam_context,
    fetch_and_save_submission,
    fetch_id_file,
    load_local_submission,
)
from models import Session as ExamSession
from models import User
from plan_assembler import QuestionPicker, load_pool
from schemas import (
    AnswerRequest,
    AnswerResponse,
    AssignmentOption,
    ComplaintRequest,
    ComplaintResponse,
    FetchSubmissionRequest,
    FetchSubmissionResponse,
    InvalidateSessionRequest,
    InvalidateSessionResponse,
    LookupResponse,
    PreviewRequest,
    ResendGradeEmailsRequest,
    PreviewResponse,
    ResultsResponse,
    SessionSummary,
    StartRequest,
    StartResponse,
    TimeoutRequest,
    TimeoutResponse,
)

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

_GITHUB_USERNAME_RE = _re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$")

# Session statuses an admin can set to let a student sit the exam again:
#   "invalidated"    — the exam didn't go through; the sitting is discarded and
#                      hidden from the dashboard/exports/grade emails.
#   "retake_enabled" — the sitting is fine, the student is simply allowed another go.
# The one-time-use lock in /api/auth/start and /api/exam/lookup ignores both.
RETAKE_UNLOCKING_STATUSES = ("invalidated", "retake_enabled")

# ---------------------------------------------------------------------------
# ID mapping: CSV loaded from GCS → in-memory lookup tables
# ---------------------------------------------------------------------------

import csv
import io
import threading

_ID_MAP_LOCK = threading.Lock()

# by_full_id:   "123456789" → "ישראל ישראלי"
# by_last5:     "56789"     → [("123456789", "ישראל ישראלי"), ...]
# by_name:      "ישראל ישראלי" → "123456789"  (reverse; only unambiguous names)
_by_full_id:  dict[str, str]                    = {}
_by_last5:    dict[str, list[tuple[str, str]]]  = {}
_by_name:     dict[str, str]                    = {}  # for classroom-roster fallback

_ID_MAP_GCS_PATH = os.environ.get("ID_MAPPING_GCS_PATH", "private/id_mapping.csv")

# Secondary username→ID fallback map: loaded from GCS at startup.
# Only consulted when id.txt is missing/empty/default — never authoritative.
_USERNAME_FALLBACK_LOCK = threading.Lock()
_username_fallback_map: dict[str, str] = {}  # lowercase github_username → last5 student ID
_USERNAME_FALLBACK_GCS_PATH = os.environ.get(
    "USERNAME_FALLBACK_MAP_GCS_PATH", "private/github_username_fallback_ids.csv"
)

# ---------------------------------------------------------------------------
# Admin page cache — keyed by assignment name, holds the last computed result
# for each of the three expensive endpoints.  Each entry:
#   {"data": <response dict>, "ts": <time.time() float>}
# Populated on first request; refreshed in the background on every subsequent
# request so the next caller always gets a fresh result.
# ---------------------------------------------------------------------------
import time as _time

_admin_cache_lock = threading.Lock()
_admin_cache: dict[str, dict[str, dict]] = {}
# structure: _admin_cache[assignment][endpoint] = {"data": ..., "ts": ...}
# endpoint keys: "aggregate", "stats", "question_stats"

# Max age (seconds) a cached admin snapshot may be served before it's treated as a
# miss and recomputed synchronously. Without this, a stale per-instance snapshot
# could be served indefinitely (the background refresh only updates the instance
# that handled the request, and can fail), so new exams stopped appearing on the
# dashboard. A short TTL bounds staleness across all instances/regions; the cost
# on expiry is one fresh GCS read (~seconds) for the request that triggers it.
_ADMIN_CACHE_TTL = int(os.environ.get("ADMIN_CACHE_TTL_SECONDS", "120"))


def _cache_get(assignment: str, endpoint: str):
    with _admin_cache_lock:
        entry = _admin_cache.get(assignment, {}).get(endpoint)
        if entry and (_time.time() - entry["ts"]) <= _ADMIN_CACHE_TTL:
            return entry["data"], entry["ts"]
    return None, None


def _cache_set(assignment: str, endpoint: str, data: dict):
    with _admin_cache_lock:
        _admin_cache.setdefault(assignment, {})[endpoint] = {
            "data": data,
            "ts": _time.time(),
        }


def _bg_refresh_stats(assignment: str):
    """Background task: recompute the cached admin endpoints for an assignment.
    (The grades aggregate is no longer warmed here — the dashboard reads it live from the
    result_summary table via /aggregate_fast; see MULTI_COURSE_MIGRATION §4.10.)"""
    try:
        admin_assignment_stats(assignment, force=True, background_tasks=None)
    except Exception as exc:
        print(f"[AdminCache] bg refresh stats/{assignment} failed: {exc}")

    try:
        from database import SessionLocal
        db = SessionLocal()
        try:
            admin_question_stats(assignment, force=True, background_tasks=None, db=db)
        finally:
            db.close()
    except Exception as exc:
        print(f"[AdminCache] bg refresh question-stats/{assignment} failed: {exc}")


def _warm_admin_cache_async() -> None:
    """Pre-compute the admin dashboard cache for the active assignment in a
    background thread at startup.

    The cache lives in process memory, so a cold start or a fresh deploy starts
    with an empty cache and the first admin page load would otherwise pay the
    full (GCS + Calendar + Sheets + DB) compute cost synchronously. Warming it
    here means that after a deploy (or any new instance) the cache is populated
    shortly after boot, off the request path. Runs as a daemon thread so it
    never blocks startup/readiness; all failures are swallowed.
    """
    assignment = os.environ.get("ASSIGNMENT_NAME", DEFAULT_ASSIGNMENT)

    def _run() -> None:
        try:
            print(f"[AdminCache] startup warm for '{assignment}' starting…")
            _bg_refresh_stats(assignment)
            print(f"[AdminCache] startup warm for '{assignment}' complete.")
        except Exception as exc:
            print(f"[AdminCache] startup warm failed: {exc}")

    threading.Thread(target=_run, name="admin-cache-warm", daemon=True).start()


def _load_id_mapping() -> dict:
    """
    Load id_mapping.csv from GCS into the two in-memory lookup dicts.
    Handles the professor's format: שם פרטי, שם משפחה, מספר זיהוי, [קבוצות].
    Also accepts the canonical format: full_id, hebrew_name.
    Returns {"loaded": N, "skipped": N, "collisions": N}.
    """
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        print("[ID Map] GCS_SUBMISSIONS_BUCKET not set — skipping ID mapping load.")
        return {"loaded": 0, "skipped": 0, "collisions": 0}

    from github_stub import _gcs_client
    bucket  = _gcs_client.bucket(bucket_name)
    blob    = bucket.blob(_ID_MAP_GCS_PATH)
    try:
        raw = blob.download_as_text(encoding="utf-8-sig")
    except Exception as exc:
        print(f"[ID Map] Could not load {_ID_MAP_GCS_PATH}: {exc}")
        return {"loaded": 0, "skipped": 0, "collisions": 0}

    reader  = csv.DictReader(io.StringIO(raw))
    headers = [h.strip().strip('"') for h in (reader.fieldnames or [])]

    # Detect format
    has_canonical  = "full_id" in headers and "hebrew_name" in headers
    has_professor  = "מספר זיהוי" in headers and "שם פרטי" in headers and "שם משפחה" in headers

    new_full: dict[str, str]                    = {}
    new_last5: dict[str, list[tuple[str, str]]] = {}
    loaded = skipped = 0

    for row in reader:
        # Strip BOM / quotes from keys
        row = {k.strip().strip('"'): v.strip() for k, v in row.items()}

        if has_canonical:
            full_id     = _re.sub(r"\D", "", row.get("full_id", ""))
            hebrew_name = row.get("hebrew_name", "").strip()
        elif has_professor:
            full_id     = _re.sub(r"\D", "", row.get("מספר זיהוי", ""))
            first       = row.get("שם פרטי", "").strip()
            last        = row.get("שם משפחה", "").strip()
            hebrew_name = f"{first} {last}".strip()
        else:
            skipped += 1
            continue

        if len(full_id) != 9:
            print(f"[ID Map] Skipping malformed full_id {full_id!r} (expected 9 digits)")
            skipped += 1
            continue

        new_full[full_id] = hebrew_name
        suffix = full_id[-5:]
        new_last5.setdefault(suffix, []).append((full_id, hebrew_name))
        loaded += 1

    # Count last-5 collisions (suffixes with more than one entry)
    collisions = sum(1 for v in new_last5.values() if len(v) > 1)
    if collisions:
        print(f"[ID Map] WARNING: {collisions} last-5-digit suffix collision(s) — "
              "students who wrote only 5 digits and share a suffix will be unresolvable.")

    # Build reverse map (name → full_id); skip names that appear more than once
    name_counts: dict[str, int] = {}
    for full_id, name in new_full.items():
        name_counts[name] = name_counts.get(name, 0) + 1
    new_by_name = {name: fid for fid, name in new_full.items() if name_counts[name] == 1}

    with _ID_MAP_LOCK:
        _by_full_id.clear()
        _by_full_id.update(new_full)
        _by_last5.clear()
        _by_last5.update(new_last5)
        _by_name.clear()
        _by_name.update(new_by_name)

    print(f"[ID Map] Loaded {loaded} entries, skipped {skipped}, collisions {collisions}.")
    return {"loaded": loaded, "skipped": skipped, "collisions": collisions}


def _load_username_fallback_map() -> int:
    """
    Load github_username_fallback_ids.csv from GCS into _username_fallback_map.
    Returns number of entries loaded. Never raises — errors are logged and ignored.
    """
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        return 0
    try:
        from github_stub import _gcs_client
        text = _gcs_client.bucket(bucket_name).blob(_USERNAME_FALLBACK_GCS_PATH).download_as_text(encoding="utf-8-sig")
        new_map: dict[str, str] = {}
        for row in csv.DictReader(io.StringIO(text)):
            raw_sid = (row.get("Student ID") or "").strip()
            gh      = (row.get("GitHub Username") or "").strip()
            sid     = _re.sub(r"\D", "", raw_sid)
            if not sid or not gh or sid == "12345":
                continue
            new_map[gh.lower()] = sid
        with _USERNAME_FALLBACK_LOCK:
            _username_fallback_map.clear()
            _username_fallback_map.update(new_map)
        print(f"[Username Fallback] Loaded {len(new_map)} entries from {_USERNAME_FALLBACK_GCS_PATH}.")
        return len(new_map)
    except Exception as exc:
        print(f"[Username Fallback] Could not load {_USERNAME_FALLBACK_GCS_PATH}: {exc}")
        return 0


# ---------------------------------------------------------------------------
# Assignment routing map: full_id → assignment_name
# Loaded from private/required_students_{assignment}.json on GCS at startup.
# ---------------------------------------------------------------------------

_assignment_map: dict[str, str] = {}  # full_id (9-digit str) → assignment_name


def _load_assignment_map() -> None:
    global _assignment_map
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        return
    new_map: dict[str, str] = {}
    try:
        from github_stub import _gcs_client
        bucket = _gcs_client.bucket(bucket_name)
        for aname in KNOWN_ASSIGNMENTS:
            blob_path = f"private/required_students_{aname}.json"
            try:
                ids: list = json.loads(bucket.blob(blob_path).download_as_text())
                for full_id in ids:
                    new_map[str(full_id).strip()] = aname
            except Exception:
                pass  # file missing for this assignment — skip silently
        _assignment_map = new_map
        print(f"[AssignmentMap] Loaded {len(_assignment_map)} student→assignment mappings.")
    except Exception as exc:
        print(f"[AssignmentMap] Could not load: {exc}")


def _resolve_github_to_full_id(github_username: str) -> Optional[str]:
    """Try to resolve a GitHub username to a 9-digit student full_id."""
    uname_lower = github_username.lower()

    # 1. username fallback CSV → last5 → full_id
    with _USERNAME_FALLBACK_LOCK:
        last5 = _username_fallback_map.get(uname_lower)
    if last5:
        with _ID_MAP_LOCK:
            matches = _by_last5.get(last5, [])
        if len(matches) == 1:
            return matches[0][0]

    # 2. GitHub Classroom roster
    try:
        from roster_utils import lookup_by_github_username
        entry = lookup_by_github_username(github_username)
        if entry and getattr(entry, "student_id", None):
            sid = _re.sub(r"\D", "", str(entry.student_id))
            if len(sid) == 9:
                return sid
    except Exception:
        pass

    return None


def resolve_student_name(
    student_id: Optional[str],
    full_id_from_repo: Optional[str],
    current_status: Optional[str],
) -> tuple[Optional[str], Optional[str], str]:
    """
    Given the id.txt-derived values, return (full_id, hebrew_name, updated_status).

    Resolution chain:
      - If full_id_from_repo is set (9 digits): look up directly in by_full_id.
      - Else if student_id is set (5 digits): look up in by_last5.
        - Exactly one match → resolved.
        - Zero matches     → name_not_in_roster.
        - Multiple matches → ambiguous_5_digit_match (log warning).
      - If the incoming status is already an error (missing_file, etc.) pass through.
    """
    if current_status not in ("ok_9_digits", "ok_5_digits"):
        # id.txt itself had a problem — don't upgrade the status
        return full_id_from_repo, None, current_status or "missing_file"

    with _ID_MAP_LOCK:
        if full_id_from_repo:
            name = _by_full_id.get(full_id_from_repo)
            if name:
                return full_id_from_repo, name, "ok"
            return full_id_from_repo, None, "name_not_in_roster"

        if student_id:
            matches = _by_last5.get(student_id, [])
            if len(matches) == 1:
                resolved_full_id, name = matches[0]
                return resolved_full_id, name, "ok"
            if len(matches) == 0:
                return None, None, "name_not_in_roster"
            # Ambiguous
            print(f"[ID Map] Ambiguous 5-digit match for student_id={student_id!r}: "
                  f"{[m[0] for m in matches]}")
            return None, None, "ambiguous_5_digit_match"

    return None, None, current_status or "missing_file"


def _validate_github_usernames() -> None:
    """Warn (never crash) on any stored github_username that fails the GitHub format check."""
    from database import SessionLocal
    import sqlalchemy
    db = SessionLocal()
    try:
        rows = db.execute(
            sqlalchemy.text("SELECT DISTINCT github_username FROM sessions WHERE github_username IS NOT NULL")
        ).fetchall()
        bad = [r[0] for r in rows if not _GITHUB_USERNAME_RE.match(r[0])]
        if bad:
            print(f"[Startup] WARNING: {len(bad)} session(s) have malformed github_username values:")
            for u in bad:
                print(f"  - {u!r}")
        else:
            print(f"[Startup] github_username format check passed ({len(rows)} distinct value(s)).")
    except Exception as exc:
        print(f"[Startup] github_username validation skipped: {exc}")
    finally:
        db.close()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    # These startup maps are all Operating-Systems-era mechanisms; a course deployment
    # that ran them would pull another course's data into memory and never read it. Each
    # is gated on the property that actually makes it relevant.

    # GitHub identity plumbing: the username→ID fallback map and the stored-username
    # format check only mean anything where a submission arrives from a repo. Gated on
    # intake mechanism, not on COURSE_ID — a future course could still use GitHub.
    if serves_github(KNOWN_ASSIGNMENTS):
        _validate_github_usernames()
        _load_username_fallback_map()

    # Per-student assignment routing (private/required_students_<name>.json) splits one
    # cohort across different assignments. That is an OS-era arrangement; other courses
    # have every student do every assignment, so there is nothing to route.
    if not COURSE_ID:
        _load_assignment_map()

    # Roster (9-digit ID → Hebrew name). OS needs it because a GitHub submission carries
    # no name. A course only needs it if it has a roster at all — Linear Algebra takes the
    # name from the form — so it loads only where the course points the path itself.
    # Without this gate a course service silently loads the OS roster from the default.
    if not COURSE_ID or os.environ.get("ID_MAPPING_GCS_PATH", "").strip():
        _load_id_mapping()
    _warm_admin_cache_async()
    yield


app = FastAPI(title="Automated Oral Exam API", version="1.0.0", lifespan=_lifespan)

# ---------------------------------------------------------------------------
# One-time resource loading (done at startup, not per-request)
# ---------------------------------------------------------------------------

def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _parse_id_txt(
    content: Optional[str], error: Optional[str]
) -> tuple[Optional[str], Optional[str], str, Optional[str]]:
    """
    Parse id.txt content into (student_id, full_id_from_repo, status, detail).

    student_id       — 5-digit short form (last 5 digits of full_id)
    full_id_from_repo — 9-digit full ID (None when student wrote only 5 digits)
    status           — id_resolution_status value (ok_9_digits, ok_5_digits, etc.)
    detail           — extra context for wrong_length / fetch_error, else None
    """
    if error == "404":
        return None, None, "missing_file", None
    if error is not None:
        return None, None, "fetch_error", error[:200]
    if not content or not content.strip():
        return None, None, "empty_file", None

    digits = _re.sub(r"\D", "", content)

    if not digits:
        return None, None, "no_digits", None
    if len(digits) == 9:
        return digits[-5:], digits, "ok_9_digits", None
    if len(digits) == 5:
        return digits, None, "ok_5_digits", None
    return None, None, "wrong_length", f"found {len(digits)} digits"


def _prompt_fingerprint(path: str, text: str) -> str:
    """Identify a loaded prompt unambiguously in the logs: which file, how big, and a
    short content hash. Two deployments reading different prompts are then obvious from
    the logs alone, without guessing from behaviour."""
    import hashlib
    return (f"{path}  ({len(text):,} chars, "
            f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]})")


try:
    EXAMINER_PROMPT      = _read_file(EXAMINER_PROMPT_PATH)
    GRADER_PROMPT        = _read_file(GRADER_PROMPT_PATH)
    CODE_REVIEWER_PROMPT = _read_file(CODE_REVIEWER_PROMPT_PATH)

    from config import COURSE_ID as _COURSE_ID
    print("[*] Loaded system prompts.")
    print(f"[prompts] COURSE_ID={_COURSE_ID!r} "
          f"({'course-scoped courses/<id>/rendered/' if _COURSE_ID else 'legacy backend/prompts/'})")
    print(f"[prompts]   examiner       {_prompt_fingerprint(EXAMINER_PROMPT_PATH, EXAMINER_PROMPT)}")
    print(f"[prompts]   grader         {_prompt_fingerprint(GRADER_PROMPT_PATH, GRADER_PROMPT)}")
    print(f"[prompts]   code_reviewer  {_prompt_fingerprint(CODE_REVIEWER_PROMPT_PATH, CODE_REVIEWER_PROMPT)}")
except Exception as e:
    raise RuntimeError(f"Failed to load required resources on startup: {e}")

# Per-assignment resources loaded on demand and cached
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_assignment_cache: dict = {}

def _get_assignment_resources(assignment_name: str) -> tuple:
    """Returns (question_pool, assignment_readme) for the given assignment, cached."""
    if assignment_name == "austin-a":
        return {}, ""

    if assignment_name not in _assignment_cache:
        assign_dir  = os.path.join(_BACKEND_DIR, "assignments")
        pool_path   = os.path.join(assign_dir, f"{assignment_name}_question_pool.json")
        readme_path = os.path.join(assign_dir, f"{assignment_name}_readme.md")
        try:
            _assignment_cache[assignment_name] = (
                load_pool(pool_path),
                _read_file(readme_path),
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Assignment '{assignment_name}' not found on this server."
            )
    return _assignment_cache[assignment_name]


def _resolve_action_file(action_file: str | None, assignment_name: str) -> str | None:
    """
    The examiner often outputs just the basename (e.g. 'pre_rate_limiter.sh') instead of the
    full path ('.claude/hooks/pre_rate_limiter.sh'). Resolve to the matching full path so the
    frontend file-tab switch and line highlight work correctly.
    """
    if not action_file:
        return action_file
    expected = ASSIGNMENT_FILES.get(assignment_name, STUDENT_FILES)
    if action_file in expected:
        return action_file
    basename = action_file.replace("\\", "/").split("/")[-1]
    for f in expected:
        if f.replace("\\", "/").split("/")[-1] == basename:
            return f
    return action_file


def _examiner_prompt_for_language(base_prompt: str, language: str) -> str:
    """
    Return the examiner prompt adapted for the given language.
    For Hebrew (default) the prompt is returned unchanged.
    For English, targeted replacements are applied so that:
      - The language rule is flipped ("MUST be in English")
      - The JSON schema comment matches
      - All hardcoded Hebrew response strings are replaced with English equivalents
    Doing targeted replacements (not just appending) avoids conflicts with the
    prompt's own "MUST be strictly in Hebrew" instruction, which would otherwise win.
    """
    if language != "en":
        return base_prompt

    replacements = [
        # --- Language & Style rule ---
        (
            "The conversation with the student (your `questionText`) MUST be strictly in Hebrew** "
            "(technical terms, system calls, and code snippets remain in English).",
            "The conversation with the student (your `questionText`) MUST be in English** "
            "(technical terms, system calls, and code snippets also remain in English).",
        ),
        # --- JSON schema comment ---
        (
            '"questionText": "The question in Hebrew.',
            '"questionText": "The question in English.',
        ),
        # --- Cold transition ---
        (
            '"נעבור לקובץ הבא." (Let\'s move to the next file)',
            '"Let\'s move to the next file."',
        ),
        # --- Switch rejection ---
        (
            '"כל סטודנט רשאי לדלג על שאלה אחת בלבד. ניגש לשאלה." '
            "(Every student may skip only one question)",
            '"Every student may skip only one question. Let\'s continue with the question."',
        ),
        # --- Hostility response ---
        (
            '"הבחינה ממשיכה. אנא ענה על השאלה." (The exam continues. Please answer)',
            '"The exam continues. Please answer the question."',
        ),
        # --- Distress closing message ---
        (
            '"אני רואה שזה מצב קשה עבורך. הבחינה מסתיימת כעת. '
            'המתרגל יקבל הודעה ויצור איתך קשר בהקדם כדי לתאם את ההמשך." '
            "(I can see this is a difficult moment for you. The exam is ending now. "
            "The TA will be notified and will contact you shortly to arrange next steps. "
            "Take care of yourself.)",
            '"I can see this is a difficult moment for you. The exam is ending now. '
            'The TA will be notified and will contact you shortly to arrange next steps. '
            'Take care of yourself."',
        ),
        # --- RE_ASK message ---
        (
            '"נראה שתשובתך לא הושלמה. אנא ענה שוב על השאלה." '
            "(Your answer seems incomplete. Please answer again)",
            '"Your answer seems incomplete. Please answer again."',
        ),
        # --- Missing files question ---
        (
            '"מה היה אמור לעשות הקובץ הזה ומדוע הוא לא הוגש?" '
            "(What was this file supposed to do and why wasn't it submitted?)",
            '"What was this file supposed to do and why wasn\'t it submitted?"',
        ),
    ]

    prompt = base_prompt
    for old, new in replacements:
        prompt = prompt.replace(old, new)
    return prompt


def _get_anthropic_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set in environment.")
    return anthropic.Anthropic(api_key=api_key)


def _resolve_identity_from_prior_blob(
    github_username: str, current_assignment: Optional[str]
) -> tuple[Optional[str], Optional[str]]:
    """
    Reuse a student's verified identity from a previous assignment's result blob.

    The same github_username is the same person across assignments, and prior
    blobs already hold a resolved (and often hand-checked) full_id + hebrew_name.
    That makes this the most reliable identity source — especially for an
    assignment whose repos carry no id.txt (e.g. assignment-3). Returns
    (full_id, hebrew_name) or (None, None). Username is matched case-insensitively.
    """
    uname = (github_username or "").strip()
    if not uname:
        return None, None
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        return None, None

    def _extract(data: dict) -> tuple[Optional[str], Optional[str]]:
        fid  = (data.get("full_id") or "").strip()
        name = (data.get("hebrew_name") or "").strip()
        return (fid or None, name or None)

    try:
        from github_stub import _gcs_client
        bucket = _gcs_client.bucket(bucket_name)
        prior = [a for a in KNOWN_ASSIGNMENTS if a != current_assignment]

        # Fast path: exact blob name (covers the vast majority).
        for aname in prior:
            try:
                data = json.loads(bucket.blob(f"results/{aname}/{uname}.json").download_as_text())
            except Exception:
                continue
            fid, name = _extract(data)
            if fid and name:
                return fid, name

        # Robust path: case-insensitive scan (covers username case differences).
        target = f"{uname.lower()}.json"
        for aname in prior:
            try:
                for blob in bucket.list_blobs(prefix=f"results/{aname}/"):
                    if blob.name.rsplit("/", 1)[-1].lower() == target:
                        fid, name = _extract(json.loads(blob.download_as_text()))
                        if fid and name:
                            return fid, name
                        break
            except Exception:
                continue
    except Exception as exc:
        print(f"[Grader BG] prior-blob identity lookup failed (non-fatal): {exc}")
    return None, None


# ---------------------------------------------------------------------------
# Background task: run grader after exam completion
# ---------------------------------------------------------------------------

def run_grader_background(session_id: str) -> None:
    """
    Runs asynchronously after the exam finishes.
    Loads the session, calls code_reviewer + grader, updates DB.
    Uses its own DB session (not the request's session — the request is already done).
    """
    from database import SessionLocal  # local import to avoid circular

    db = SessionLocal()
    try:
        session = db.query(ExamSession).filter(ExamSession.session_id == session_id).first()
        if not session:
            print(f"[Grader BG] Session {session_id} not found.")
            return

        client = _get_anthropic_client()
        transcript = json.loads(session.transcript)

        # Rebuild student_files dict from stored context (not re-fetching)
        # For code_reviewer we pass the stored context as a single "file"
        # so it gets the same code the examiner saw.
        student_files_raw = session.student_files_context or ""

        # ── Phase 1: Code Reviewer ──────────────────────────────────────────
        print(f"[Grader BG] Running code reviewer for session {session_id}...")
        try:
            files_dict = json.loads(student_files_raw) if student_files_raw.startswith("{") else {}
        except json.JSONDecodeError:
            files_dict = {"submission.c": student_files_raw}

        _assignment = session.assignment_name or "test-assignment"
        _, assignment_readme = _get_assignment_resources(_assignment)

        if _assignment == "austin-a":
            # Bypass CP Java code review entirely
            code_review_json = {
                "staticCodeQualityScore": 100,
                "studentStaticFeedback": "Competitive programming delta exam (code style not evaluated).",
                "signalBAssessment": {"level": "none", "markersFound": 0}
            }
        else:
            _scope = assignment_scope(_assignment)
            _reviewer_readme = assignment_readme
            if _scope:
                _reviewer_readme += (
                    "\n\n# Concepts the students had been taught when this was set\n"
                    f"{_scope}\n\n"
                    "Judge the submission only against these."
                )
            code_review_json, code_reviewer_model = call_code_reviewer(
                client, CODE_REVIEWER_PROMPT, _reviewer_readme, files_dict
            )
    
        # ── Phase 1b: Reviewer validator (hallucination guard) ───────────────
        # Audits the reviewer's deductions for over-penalization. When it finds unfair ones it
        # RESTORES the wrongly-removed points (only ever raises the score, never lowers) and
        # minimally edits the student feedback — this feeds the corrected static score into the
        # final grade below. Gated on a flag and on score<100 (a perfect score has no deduction
        # to challenge). The original score/feedback are preserved for audit. See MIGRATION §4.9.
        _validator_flag = os.environ.get("REVIEWER_VALIDATOR_ENABLED", "").lower() in ("1", "true", "yes")
        _cr_score = code_review_json.get("staticCodeQualityScore")
        if not _validator_flag:
            print(f"[Grader BG] validator: OFF (REVIEWER_VALIDATOR_ENABLED not set) — session {session_id}", flush=True)
        elif not isinstance(_cr_score, (int, float)):
            print(f"[Grader BG] validator: SKIPPED — code score not numeric ({_cr_score!r}) — session {session_id}", flush=True)
        elif _cr_score >= 100:
            print(f"[Grader BG] validator: SKIPPED — perfect code score {_cr_score}, nothing to challenge — session {session_id}", flush=True)
        else:
            print(f"[Grader BG] validator: RUNNING (code score {_cr_score} < 100) — session {session_id}", flush=True)
            try:
                from agents import call_reviewer_validator
                from config import REVIEWER_VALIDATOR_PROMPT_PATH
                validator_prompt = _read_file(REVIEWER_VALIDATOR_PROMPT_PATH)
                validation_json, _vmodel = call_reviewer_validator(
                    client, validator_prompt, assignment_readme, files_dict, code_review_json, None
                )
                code_review_json["reviewerValidation"] = validation_json  # rides into the blob
                _n_ch = len(validation_json.get("challenges", []))
                orig_score = code_review_json["staticCodeQualityScore"]
                if validation_json.get("any_unfair_deductions"):
                    corrected = validation_json.get("corrected_static_score")
                    if isinstance(corrected, (int, float)):
                        new_score = max(orig_score, min(100, int(round(corrected))))  # only restore
                        if new_score != orig_score:
                            code_review_json["originalStaticCodeQualityScore"] = orig_score
                            code_review_json["staticCodeQualityScore"] = new_score
                    new_fb = (validation_json.get("corrected_student_feedback") or "").strip()
                    if new_fb:
                        code_review_json["originalStudentStaticFeedback"] = code_review_json.get("studentStaticFeedback", "")
                        code_review_json["studentStaticFeedback"] = new_fb
                print(f"[Grader BG] validator: DONE (model={_vmodel}) — {_n_ch} challenge(s), "
                      f"unfair={validation_json.get('any_unfair_deductions')}, "
                      f"static {orig_score}→{code_review_json['staticCodeQualityScore']} — session {session_id} — "
                      f"{(validation_json.get('summary') or '')[:160]}", flush=True)
            except Exception as ve:  # noqa: BLE001 — never fatal, grade proceeds on the original review
                print(f"[Grader BG] validator: FAILED (non-fatal, kept original review): {ve} — session {session_id}", flush=True)

        # ── Phase 2: Grader ─────────────────────────────────────────────────
        print(f"[Grader BG] Running grader for session {session_id}...")
        signal_b = code_review_json.get("signalBAssessment", {})

        # Build extra context for the grader based on timeout, switch, and re-ask events
        extra_notes_parts = []

        # ── Timeout ──────────────────────────────────────────────────────────
        if session.timed_out:
            meta = json.loads(session.timeout_metadata or "{}")
            timed_out_at  = meta.get("timed_out_at_question", "?")
            not_reached   = meta.get("questions_not_reached", [])
            partial_qs    = meta.get("questions_partial", [])
            not_reached_str = ", ".join(str(q) for q in not_reached) if not_reached else "none"
            lines = [
                "## Exam Completion Status",
                f"TIMED OUT. The timer fired while the student was on question {timed_out_at}.",
                f"Questions with no answer text (student never reached or never started): {not_reached_str}.",
            ]
            if partial_qs:
                partial_str = ", ".join(str(q) for q in partial_qs)
                lines.append(
                    f"Question(s) {partial_str}: the timer expired before the student clicked Submit. "
                    "The text they had typed was captured and appears in the transcript as a "
                    "'timeout_partial' entry. The examiner evaluated this text and scored it normally — "
                    "treat it as a valid, scoreable answer. "
                    "The student did not choose to end the exam; the timer ended it for them."
                )
            extra_notes_parts.append("\n".join(lines))

        # ── Switch events ─────────────────────────────────────────────────────
        # Find student entries tagged as switch events and recover the original
        # question text from the preceding examiner turn.
        switch_events = []
        for i, entry in enumerate(transcript):
            if entry.get("role") == "Student" and entry.get("switch_event"):
                student_switch_text = entry.get("content", "")
                switch_at_q = entry.get("switch_at_question", "?")

                # Walk backwards to find the question that was asked (and skipped)
                original_q_text = ""
                for prev in reversed(transcript[:i]):
                    if prev.get("role") == "Examiner" and not prev.get("reask") and not prev.get("switch_replacement"):
                        original_q_text = prev.get("content", {}).get("questionText", "")
                        break

                switch_events.append(
                    f"Question {switch_at_q}: Student requested a switch.\n"
                    f"  Student's exact words: \"{student_switch_text}\"\n"
                    f"  Original question that was skipped: \"{original_q_text}\"\n"
                    f"  A replacement question at the same difficulty was provided instead."
                )

        if switch_events:
            extra_notes_parts.append(
                "## Behavioral Notes — Question Switch\n"
                + "\n".join(switch_events)
                + "\n\nGrader: the student used their one allowed switch. "
                "A replacement question at the same difficulty was provided and they answered that instead. "
                "Consider the switch in context: if the original question was on a core topic the student "
                "should have known, that is a meaningful signal. If it was peripheral, it matters less. "
                "Weigh it against their overall performance and use your judgment — do not ignore it, "
                "but do not apply a fixed penalty either."
            )

        # ── RE_ASK events ─────────────────────────────────────────────────────
        reask_events = []
        for i, entry in enumerate(transcript):
            if entry.get("role") == "Student" and entry.get("reask_triggered"):
                weird_answer = entry.get("content", "")
                q_num = "?"
                for prev in reversed(transcript[:i]):
                    if prev.get("role") == "Examiner" and not prev.get("reask"):
                        q_num = prev.get("content", {}).get("questionNumber", "?")
                        break
                reask_events.append(
                    f"Question {q_num}: Examiner issued a RE_ASK after the student's first response "
                    f"(exact text: \"{weird_answer}\"). Reason may be a malformed reply or a structural "
                    f"topic mismatch — see transcript for context. Their second response is what was scored."
                )

        if reask_events:
            extra_notes_parts.append(
                "## Behavioral Notes — Re-Ask Events\n"
                + "\n".join(reask_events)
                + "\n\nGrader: the second response is the one that was evaluated. "
                "The first malformed attempt is noted for context only."
            )

        extra_notes = "\n\n".join(extra_notes_parts)

        grader_prompt_to_use = (
            _read_file(os.path.join(_BACKEND_DIR, "prompts", "grader_prompt_ut.txt"))
            if _assignment == "austin-a"
            else GRADER_PROMPT
        )
        grader_json, grader_model = call_grader(
            client, grader_prompt_to_use, assignment_readme, signal_b, transcript, extra_notes
        )

        # ── Phase 3: Mechanical grade ────────────────────────────────────────
        oral_score   = grader_json.get("oralDefenseScore", 50)
        static_score = code_review_json.get("staticCodeQualityScore", 50)
        grading_breakdown = compute_final_grade(oral_score, static_score)

        # ── Phase 2: Fetch id.txt from repo ────────────────────────────────────
        id_content, id_error = fetch_id_file(
            session.github_username or "",
            session.assignment_name or "test-assignment",
        )
        numeric_student_id, full_id_from_repo, id_status, id_detail = _parse_id_txt(
            id_content, id_error
        )
        print(
            f"[Grader BG] id.txt for {session.github_username!r}: "
            f"status={id_status!r} student_id={numeric_student_id!r} "
            f"full_id={full_id_from_repo!r}"
        )

        # Phase 3: upgrade status with name-resolution outcome
        resolved_full_id, resolved_name, id_status = resolve_student_name(
            numeric_student_id, full_id_from_repo, id_status
        )

        # Phase 3-forms: a Forms course may keep no roster at all, in which case every
        # lookup above fails and the student would be nameless in their own grade email.
        # The form asked them for their name, so use it — but only to fill a gap, never to
        # override a roster, which is staff-maintained and authoritative where it exists.
        if not resolved_name:
            form_name = student_name(
                session.github_username or "",
                session.assignment_name or "test-assignment",
            )
            if form_name:
                resolved_name = form_name
                id_status = "ok_name_from_form" if id_status in (
                    "name_not_in_roster", "missing_file", "no_digits",
                ) else id_status
                print(f"[Grader BG] name from form: {session.github_username} → {form_name}")
        # resolved_full_id may be from the CSV (authoritative) or from the repo
        final_full_id = resolved_full_id or full_id_from_repo

        # Phase 3a: prior-assignment blob — the most reliable identity source.
        # If id.txt didn't resolve and this student already has a graded blob from
        # another assignment, reuse its full_id + hebrew_name (resolved/checked
        # then). This is the primary resolver for assignments with no id.txt
        # (assignment-3), and runs before the weaker secondary-map / roster chains.
        if final_full_id is None:
            prior_full_id, prior_name = _resolve_identity_from_prior_blob(
                session.github_username or "", session.assignment_name
            )
            if prior_full_id:
                final_full_id      = prior_full_id
                resolved_name      = prior_name or resolved_name
                numeric_student_id = numeric_student_id or prior_full_id[-5:]
                id_status          = "ok_via_prior_blob"
                print(
                    f"[Grader BG] Prior-blob identity: "
                    f"{session.github_username} → {resolved_name} ({final_full_id})"
                )

        # Phase 3b: secondary username map — consulted before the classroom roster
        # because some students registered GitHub with the wrong email, making the
        # roster's name-bridge unreliable. IDs are manually curated; status is tagged.
        _FALLBACK_TRIGGERS = {
            "missing_file", "empty_file", "no_digits", "wrong_length",
            "fetch_error", "name_not_in_roster", "ambiguous_5_digit_match",
        }
        _is_placeholder = (numeric_student_id == "12345")
        if final_full_id is None and (id_status in _FALLBACK_TRIGGERS or _is_placeholder):
            try:
                with _USERNAME_FALLBACK_LOCK:
                    fallback_last5 = _username_fallback_map.get(
                        (session.github_username or "").lower()
                    )
                if fallback_last5:
                    with _ID_MAP_LOCK:
                        matches = _by_last5.get(fallback_last5, [])
                    if len(matches) == 1:
                        fb_full_id, fb_name = matches[0]
                        numeric_student_id = fallback_last5
                        final_full_id      = fb_full_id
                        resolved_name      = fb_name
                        id_status          = "ok_via_secondary_username_map"
                        print(
                            f"[Grader BG] Secondary map resolved: "
                            f"{session.github_username} → {fb_name} ({fb_full_id})"
                        )
                    elif len(matches) == 0:
                        numeric_student_id = fallback_last5
                        id_status          = "secondary_map_id_not_in_roster"
                        print(
                            f"[Grader BG] Secondary map: found last5={fallback_last5!r} "
                            f"for {session.github_username} but not in id_mapping."
                        )
                    else:
                        numeric_student_id = fallback_last5
                        id_status          = "secondary_map_ambiguous"
                        print(
                            f"[Grader BG] Secondary map: last5={fallback_last5!r} "
                            f"for {session.github_username} is ambiguous in id_mapping."
                        )
            except Exception as fallback_err:
                print(f"[Grader BG] Secondary username map fallback failed (non-fatal): {fallback_err}")

        # Phase 3c: classroom-roster fallback — used when id.txt and the secondary map
        # both failed to produce a full_id. Bridges github_username → Hebrew name →
        # id_mapping reverse-lookup. Can fail if the student used a mismatched email.
        if final_full_id is None and id_status in (
            "missing_file", "empty_file", "no_digits", "wrong_length",
            "fetch_error", "name_not_in_roster", "secondary_map_id_not_in_roster",
            "secondary_map_ambiguous",
        ):
            try:
                from roster_utils import lookup_by_github_username
                roster_entry = lookup_by_github_username(session.github_username or "")
                if roster_entry:
                    with _ID_MAP_LOCK:
                        roster_full_id = _by_name.get(roster_entry.full_name_he)
                    if roster_full_id:
                        resolved_name  = roster_entry.full_name_he
                        final_full_id  = roster_full_id
                        id_status      = "ok_via_classroom_roster"
                        print(
                            f"[Grader BG] Roster fallback resolved: "
                            f"{session.github_username} → {resolved_name} ({roster_full_id})"
                        )
                    else:
                        resolved_name = roster_entry.full_name_he
                        id_status     = "roster_name_not_in_id_map"
                        print(
                            f"[Grader BG] Roster found name {resolved_name!r} "
                            f"but not in id_mapping — status set to {id_status}"
                        )
            except Exception as roster_err:
                print(f"[Grader BG] Classroom roster fallback failed: {roster_err}")

        print(
            f"[Grader BG] Name resolution: status={id_status!r} "
            f"full_id={final_full_id!r} name={resolved_name!r}"
        )

        # ── Write GCS result blob FIRST, then mark graded ────────────────────
        # The grade-email cron and every admin view read this blob. A session
        # marked "graded" in the DB with no blob silently drops the student's
        # email (this happened to Em8082, 2026-06: a transient blob-write failure
        # under a double-grading race left status=graded with no blob, and the
        # cron 404'd on it every morning). The previous code wrote the blob in a
        # *non-fatal* try/except AFTER committing "graded", so a blob failure was
        # swallowed and the bad state persisted. Now we write the blob with
        # retries and only commit "graded" once it is safely persisted, making
        # "graded ⟹ blob exists" an invariant. If the blob ultimately can't be
        # written we raise, leaving the session NOT graded so it can be regraded.
        bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
        if bucket_name:
            from github_stub import _gcs_client
            bucket = _gcs_client.bucket(bucket_name)
            blob_path = f"results/{session.assignment_name}/{session.github_username}.json"
            blob_data = {
                "session_id":           session.session_id,
                "github_username":      session.github_username,
                "assignment_name":      session.assignment_name,
                "start_time":           session.start_time.isoformat() if session.start_time else None,
                "status":               "graded",
                "language":             session.language,
                "timed_out":            session.timed_out,
                "timeout_metadata":     json.loads(session.timeout_metadata or "{}"),
                "switch_used":          session.switch_used,
                "student_id":           numeric_student_id,
                "full_id_from_repo":    full_id_from_repo,
                "full_id":              final_full_id,
                "hebrew_name":          resolved_name,
                "id_resolution_status": id_status,
                "id_resolution_detail": id_detail,
                "final_grade":          grading_breakdown,
                "professor_report":     grader_json.get("professorReport", ""),
                "code_review":          code_review_json,
                "grader_verdict":       grader_json,
                "transcript":           transcript,
                # debug fields kept in blob; Phase 4 API strips them from responses
                "examiner_messages":    json.loads(session.examiner_messages or "[]"),
                "picker_state":         json.loads(session.picker_state or "{}"),
                "session_seed":         session.session_seed,
                "examiner_temp":        session.examiner_temp,
                "grade_email_sent":     False,
            }
            blob_payload = json.dumps(blob_data, ensure_ascii=False, indent=2)
            blob_err = None
            for attempt in range(1, 4):
                try:
                    bucket.blob(blob_path).upload_from_string(
                        blob_payload,
                        content_type="application/json; charset=utf-8",
                    )
                    blob_err = None
                    print(f"[Grader BG] Result blob written: {blob_path}")
                    break
                except Exception as exc:
                    blob_err = exc
                    print(f"[Grader BG] blob write attempt {attempt}/3 failed: {exc}")
                    _time.sleep(2 * attempt)
            if blob_err is not None:
                raise RuntimeError(
                    f"Result blob write failed after 3 attempts for {blob_path}: {blob_err}"
                )

        # ── Persist results to DB (only after the blob is safely written) ─────
        session.code_review          = json.dumps(code_review_json, ensure_ascii=False)
        session.grader_verdict       = json.dumps(grader_json, ensure_ascii=False)
        session.final_grade          = json.dumps(grading_breakdown, ensure_ascii=False)
        session.professor_report     = grader_json.get("professorReport", "")
        session.student_id           = numeric_student_id
        session.full_id_from_repo    = full_id_from_repo
        session.id_resolution_status = id_status
        session.id_resolution_detail = id_detail
        session.status               = "graded"
        db.commit()

        print(
            f"[Grader BG] Session {session_id} graded. "
            f"Final grade: {grading_breakdown.get('finalWeightedGrade', '?')}"
        )

        # ── Keep the result_summary read-model in sync ───────────────────────
        # Derived table behind the admin dashboard (MULTI_COURSE_MIGRATION §4.10).
        #
        # ON by default. It was opt-in while it was new and OS ran without it, but the
        # dashboard now reads /aggregate_fast exclusively — the blob-backed /aggregate it used
        # to fall back to has been removed. So a deployment without this writes no rows and its
        # assignment overview silently reports 0 examined while every per-student page works.
        # Set RESULT_SUMMARY_ENABLED=false to opt out.
        #
        # The funnel takes the exact blob dict, so the row always matches the blob, and it is
        # never fatal — a summary hiccup must not fail an otherwise-successful grading
        # (rebuild any time from the blobs, which remain the source of truth).
        # (bucket_name truthy ⟹ blob_data was built and written above)
        _summary_flag = os.environ.get("RESULT_SUMMARY_ENABLED", "true").lower() \
            not in ("0", "false", "no")
        if bucket_name and _summary_flag:
            try:
                from result_summary import upsert_summary_from_blob
                upsert_summary_from_blob(db, blob_data)
                print(f"[Grader BG] result_summary: row upserted for "
                      f"{session.github_username}/{session.assignment_name}", flush=True)
            except Exception as se:  # noqa: BLE001
                print(f"[Grader BG] result_summary: upsert FAILED (non-fatal): {se}", flush=True)
        else:
            print("[Grader BG] result_summary: OFF (RESULT_SUMMARY_ENABLED=false) — the "
                  "admin overview for this assignment will report 0 examined", flush=True)

        # One-line grading summary — the at-a-glance record for every grading event.
        print(f"[Grader BG] SUMMARY session={session_id} student={session.github_username} "
              f"assignment={session.assignment_name} oral={oral_score} "
              f"static={code_review_json.get('staticCodeQualityScore')} "
              f"final={grading_breakdown.get('finalWeightedGrade')} "
              f"authorship={grader_json.get('authorshipAssessment')} "
              f"validator_corrected={'originalStaticCodeQualityScore' in code_review_json}", flush=True)

    except Exception as e:
        print(f"[Grader BG] ERROR grading session {session_id}: {e}")
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/admin/fetch-submission
# ---------------------------------------------------------------------------

@app.post("/api/admin/fetch-submission", response_model=FetchSubmissionResponse)
def fetch_submission(body: FetchSubmissionRequest) -> FetchSubmissionResponse:
    """
    Pull one student's submitted files from their GitHub Classroom repository
    and save them to GCS at {assignment_name}/{github_username}/.

    Call this ONCE per student before starting their exam.
    The exam endpoints (start, answer) read from GCS — they never contact GitHub directly.

    Requires GITHUB_ORG to be set in the environment.
    """
    github_username = body.github_username.strip()

    if not github_username:
        raise HTTPException(status_code=400, detail="github_username cannot be empty.")

    try:
        result = fetch_and_save_submission(github_username, body.assignment_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"GitHub fetch failed: {exc}")

    if result.files_missing:
        msg = (
            f"Fetched {len(result.files_saved)}/{len(result.files_saved) + len(result.files_missing)} "
            f"files. Missing: {', '.join(result.files_missing)}. "
            f"Exam can still proceed — missing files will be flagged."
        )
    else:
        msg = f"All {len(result.files_saved)} file(s) saved successfully."

    return FetchSubmissionResponse(
        github_username = result.github_username,
        repo            = result.repo,
        files_saved     = result.files_saved,
        files_missing   = result.files_missing,
        message         = msg,
    )


# ---------------------------------------------------------------------------
# POST /api/auth/start
# ---------------------------------------------------------------------------

@app.post("/api/auth/start", response_model=StartResponse)
def start_exam(
    body: StartRequest,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db),
) -> StartResponse:
    """
    Initialise a new exam session for a student.

    PREREQUISITE: call POST /api/admin/fetch-submission first to download
    the student's files from GitHub.  This endpoint only reads from disk.

    Steps:
      1. Upsert user record (github_username used as student_id).
      2. One-time use check (any existing session for this github_username blocks).
      3. Fetch files from GitHub.
      4. Initialise QuestionPicker, pick Q1 (medium).
      5. Call examiner for Q1.
      6. Persist session to DB.
      7. Return session_id + Q1 question text.
    """
    github_username = body.github_username.strip()
    if not github_username:
        raise HTTPException(status_code=400, detail="github_username cannot be empty.")

    assignment_name = (body.assignment_name or os.environ.get("ASSIGNMENT_NAME", "test-assignment")).strip()
    is_qa = assignment_name in QA_ASSIGNMENTS
    print(f"[start] github={github_username!r}  assignment={assignment_name!r}  qa={is_qa}  persona={body.persona!r}")

    # One-time use lock: block retakes only when a session exists that the admin
    # hasn't cleared (see RETAKE_UNLOCKING_STATUSES). Test identities in
    # config.UNLIMITED_RETAKE_IDS are exempt so staff dry-runs don't need someone on call to
    # clear a sitting each time.
    if not is_qa and not is_unlimited_retake(github_username):
        existing = (
            db.query(ExamSession)
            .filter(
                ExamSession.github_username == github_username,
                ExamSession.assignment_name == assignment_name,
                ExamSession.status.notin_(RETAKE_UNLOCKING_STATUSES),
            )
            .first()
        )
        if existing:
            detail = "complaint_pending" if existing.status == "complaint_pending" else "already_started"
            raise HTTPException(status_code=409, detail=detail)

    # Upsert user record
    user = db.query(User).filter(User.github_username == github_username).first()
    if not user:
        user = User(github_username=github_username)
        db.add(user)
        db.commit()

    question_pool, assignment_readme = _get_assignment_resources(assignment_name)

    # Fetch submission from GitHub (skipped for QA — files pre-uploaded to GCS).
    if not is_qa:
        try:
            fetch_result = fetch_and_save_submission(github_username, assignment_name)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Could not fetch submission from GitHub: {exc}")
        if not fetch_result.files_saved:
            raise HTTPException(
                status_code=404,
                detail=f"No submission files found for '{github_username}' in the GitHub Classroom repository. "
                       f"Make sure the GitHub username is correct and the assignment was submitted.",
            )

    # Load files
    student_files = load_local_submission(github_username, assignment_name)

    # Include assignment instructions as the first viewable file for the student
    if assignment_readme:
        student_files = {"README.md": assignment_readme, **student_files}

    # --- UT AUSTIN DYNAMIC GENERATION BYPASS ---
    if assignment_name == "austin-a":
        local_dir = os.environ.get("LOCAL_SUBMISSIONS_DIR", "")
        student_dir = os.path.join(local_dir, github_username)
        print(f"[DEBUG] local_dir: {local_dir!r}")
        print(f"[DEBUG] looking in: {student_dir!r}")
        try:
            import glob
            
            # 1. Dynamically find the files regardless of extension (.java, .cpp, etc.)
            failed_paths = glob.glob(os.path.join(student_dir, "failed.*"))
            accepted_paths = glob.glob(os.path.join(student_dir, "accepted.*"))
            
            if not failed_paths or not accepted_paths:
                raise FileNotFoundError(f"Missing failed.* or accepted.* in {student_dir}")
                
            failed_path = failed_paths[0]
            accepted_path = accepted_paths[0]
            
            failed_filename = os.path.basename(failed_path)
            accepted_filename = os.path.basename(accepted_path)

            with open(failed_path, "r", encoding="utf-8") as f:
                failed_code = f.read()
            with open(accepted_path, "r", encoding="utf-8") as f:
                accepted_code = f.read()

            # 2. Assign the dynamic filenames to the frontend viewer
            student_files = {failed_filename: failed_code, accepted_filename: accepted_code}
            if assignment_readme:
                student_files["README.md"] = assignment_readme

            from delta_generator_ut import generate_delta_pool
            print(f"[start] Generating dynamic question pool for {github_username}...")

            # 3. Pass the actual filenames into the generator 
            _raw_pool = generate_delta_pool(
                failed_filename, failed_code, 
                accepted_filename, accepted_code, 
                assignment_readme
            )
            
            import json
            import re

            # 1. If it's a string, aggressively extract the JSON structure
            if isinstance(_raw_pool, str):
                _match = re.search(r'(\{.*\}|\[.*\])', _raw_pool, re.DOTALL)
                if _match:
                    try:
                        _raw_pool = json.loads(_match.group(1))
                    except Exception:
                        pass
            
            # 2. If it parsed into a dictionary (e.g., {"questions": [...]}), extract the list
            if isinstance(_raw_pool, dict):
                for val in _raw_pool.values():
                    if isinstance(val, list):
                        _raw_pool = val
                        break
                else:
                    _raw_pool = [_raw_pool]
            
            # 3. Enforce the final contract for QuestionPicker (List[Dict])
            if not isinstance(_raw_pool, list):
                _raw_pool = []
            question_pool = [q for q in _raw_pool if isinstance(q, dict)]

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Failed to generate delta pool: {e}")  
    # --- END BYPASS ---


    # 3. Build exam context and initialise picker
    full_context = build_exam_context(assignment_readme, student_files)


    # Narrow the examiner to what this assignment's students had been taught. The pool is
    # already filtered on the same list, but the examiner writes the actual question text
    # from a topic — a fair topic can still be phrased in terms of later material.
    # Rides in the Q1 message, so it costs tokens once per exam rather than per turn.
    _scope = assignment_scope(assignment_name)
    if _scope:
        full_context += (
            "\n\n# Concepts in scope for this assignment\n"
            f"{_scope}\n\n"
            "This is what the students had been taught when this assignment was set. Keep "
            "every question, and every follow-up, inside it — phrase topics using these "
            "concepts rather than more advanced ones the student has not yet met."
        )

    # Include pre-generated man pages AFTER building context — student viewer only, not in AI prompt
    _man_pages_path = os.path.join(ASSIGN_DIR, f"{assignment_name}_man_pages.txt")
    if os.path.exists(_man_pages_path):
        with open(_man_pages_path, "r", encoding="utf-8") as _f:
            student_files["man_pages.txt"] = _f.read()
    session_seed = random.randint(0, 2**32)
    examiner_temp = round(random.uniform(0.2, 0.4), 2)
    picker = QuestionPicker(question_pool, seed=session_seed, silent=True)

    q1_options = picker.peek_options(["medium", "medium"])
    if not any(q1_options):
        raise HTTPException(status_code=500, detail="Could not pick Q1 — question pool may be empty.")

    print(f"[Picker] Q1 options offered to examiner:")
    for label, opt in zip(["medium-1", "medium-2"], q1_options):
        if opt is not None:
            print(f"  [{label}] {opt['files']} / {opt['focus'][:55]} ({opt['difficulty']})")
        else:
            print(f"  [{label}] (not available)")

    # 4. Call examiner for Q1
    client = _get_anthropic_client()
    # emergency_client = _get_emergency_anthropic_client()
    emergency_client = None
    q1_llm_called_at = datetime.utcnow().isoformat(timespec="seconds")
    language = (body.language or "he").lower()
    
    if assignment_name == "austin-a":
        examiner_prompt = _read_file(os.path.join(_BACKEND_DIR, "prompts", "examiner_prompt_ut.txt"))
    else:
        examiner_prompt = _examiner_prompt_for_language(EXAMINER_PROMPT, language)
        
    # try:
    #     examiner_messages, tool_use_id, examiner_json, model_used = call_examiner_q1(
    #         client, examiner_prompt, full_context, q1_options, picker, examiner_temp,
    #         emergency_client=emergency_client, db=db, course_id=COURSE_ID,
    #         assignment_name=assignment_name,
    #     )
    # except ExaminerOutputUnusable as exc:
    #     print(f"[start] !! no question produced for {github_username!r} "
    #           f"({assignment_name}): {exc}", flush=True)
    #     raise HTTPException(status_code=503, detail="examiner_no_question")


    try:
        # Strictly the 6 arguments your agents.py actually accepts
        examiner_messages, tool_use_id, examiner_json, model_used = call_examiner_q1(
            client, examiner_prompt, full_context, q1_options, picker, examiner_temp
        )
        
        # Print exactly what the LLM tried to pass to the tool
        print(f"\n[CRITICAL DEBUG EXAMINER RAW MSG]\n{examiner_messages[-1]}\n")
        
    except Exception as exc:
        print(f"[start] !! no question produced for {github_username!r} "
              f"({assignment_name}): {exc}", flush=True)
        raise HTTPException(status_code=503, detail="examiner_no_question")


    # Resolve which Q1 option the examiner chose and mark it used
    _q1_label_to_idx = {"medium-1": 0, "medium-2": 1}
    _q1_chosen_label = examiner_json.get("chosenTopicLabel")
    _q1_idx = _q1_label_to_idx.get(_q1_chosen_label, 0)
    q1 = q1_options[_q1_idx] if _q1_idx < len(q1_options) and q1_options[_q1_idx] is not None \
         else next((o for o in q1_options if o is not None), None)
    if q1 is not None:
        picker.mark_used(q1)
    print(f"[Picker] Q1 chosen: label={_q1_chosen_label!r} -> {q1['files'] if q1 else 'None'} / {q1['focus'][:55] if q1 else ''}")

    question_text   = examiner_json.get("questionText", "")
    question_number = max(1, min(examiner_json.get("questionNumber", 1), 3))
    action_params   = examiner_json.get("actionParameters") or {}
    action          = examiner_json.get("action")
    action_file     = _resolve_action_file(action_params.get("fileName"), assignment_name)
    action_code_line = action_params.get("codeLine")

    # Build initial transcript entry
    transcript = [{
        "role": "Examiner",
        "model": model_used,
        "llm_called_at": q1_llm_called_at,
        "question_shown_at": datetime.utcnow().isoformat(timespec="seconds"),
        "chosen_topic": q1,
        "offered_topic_options": [
            picker.format_topic_for_examiner(o) for o in q1_options if o is not None
        ],
        "content": examiner_json,
    }]

    # 5. Determine exam duration (accommodation students get extra time)
    id_txt_raw = student_files.get("id.txt", "").strip()
    if not id_txt_raw:
        roster_id = _resolve_github_to_full_id(github_username)
        if roster_id:
            id_txt_raw = roster_id
            print(f"[start] id.txt missing — using roster-resolved ID {roster_id!r} for accommodation check")
    # Still unresolved? Fall back to the prior-assignment blob — the same robust
    # source the grader uses. Without this, an accommodation student whose repo has
    # no id.txt and whose roster row carries no ID (e.g. assignment-3 repos) is
    # silently denied extended time at start, even though grading later identifies
    # them via their earlier blob. Only runs in that rare miss case, so it adds no
    # cost to the common path.
    if not "".join(c for c in id_txt_raw if c.isdigit()):
        prior_full_id, _prior_name = _resolve_identity_from_prior_blob(github_username, assignment_name)
        if prior_full_id:
            id_txt_raw = prior_full_id
            print(f"[start] id.txt missing & roster miss — using prior-blob ID {prior_full_id!r} for accommodation check")
    default_duration = int(os.environ.get("EXAM_DURATION_SECONDS", 960))
    try:
        extended = is_extended_time(id_txt_raw)
    except Exception as exc:
        print(f"[start] Accommodation check failed ({exc}), defaulting to standard duration.")
        extended = False
    exam_duration_seconds = EXTENDED_TIME_SECONDS if extended else default_duration
    print(f"[start] id_txt={id_txt_raw!r}  extended={'yes' if extended else 'no'}  duration={exam_duration_seconds}s")

    # --- UT AUSTIN TIMER OVERRIDE ---
    if assignment_name == "austin-a":
        exam_duration_seconds = 10800  # 3 hours in seconds
    # --------------------------------

    # 6. Persist session
    session = ExamSession(
        github_username     = github_username,
        start_time          = datetime.utcnow(),
        status              = "in-progress",
        transcript          = json.dumps(transcript, ensure_ascii=False),
        examiner_messages   = json.dumps(serialize_messages(examiner_messages), ensure_ascii=False),
        picker_state        = json.dumps(picker.to_state(), ensure_ascii=False),
        pending_tool_use_id = tool_use_id,
        turn                = 1,
        session_seed        = session_seed,
        examiner_temp       = examiner_temp,
        student_files_context = json.dumps(student_files, ensure_ascii=False),
        assignment_name        = assignment_name,
        persona                = body.persona,
        language               = language,
        github_username_manual = bool(body.github_username_manual),
        # Course-neutral identity (config.student_key_for). Written alongside
        # github_username, which stays authoritative until the reads are switched.
        student_key            = student_key_for(assignment_name, github_username),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    import hashlib as _hl
    print(f"[session:start] sid={session.session_id} github={github_username!r} "
          f"assignment={assignment_name!r} model={model_used!r} "
          f"course={_COURSE_ID or '(legacy)'} "
          f"examiner_prompt=sha256:{_hl.sha256(EXAMINER_PROMPT.encode('utf-8')).hexdigest()[:12]} "
          f"source={source_for(assignment_name)} student_key={session.student_key!r}")

    return StartResponse(
        session_id            = session.session_id,
        question_text         = question_text,
        question_number       = question_number,
        action                = action,
        action_file           = action_file,
        action_code_line      = action_code_line,
        assignment_name       = assignment_name,
        files                 = student_files,
        exam_duration_seconds = exam_duration_seconds,
    )


# ---------------------------------------------------------------------------
# POST /api/exam/answer
# ---------------------------------------------------------------------------

@app.post("/api/exam/answer", response_model=AnswerResponse)
def submit_answer(
    body: AnswerRequest,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db),
) -> AnswerResponse:
    """
    Accept a student answer, advance the exam, return the next question (or finish).

    Steps:
      1. Load session from DB.
      2. Validate answer.
      3. Reconstruct picker + examiner_messages from DB state.
      4. Build next turn message (tool_result + answer + 3 topic options).
      5. Call examiner.
      6. If FINISH_EXAM: trigger background grader, return finish message.
      7. Else: register chosen topic, persist updated state, return next question.
    """
    session = db.query(ExamSession).filter(ExamSession.session_id == body.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.status != "in-progress":
        raise HTTPException(
            status_code=400,
            detail=f"Session is already '{session.status}'. No more answers accepted."
        )

    # 2. Validate answer
    print(f"[session:answer] sid={body.session_id} github={session.github_username!r} turn={session.turn} answer_len={len(body.student_answer.strip())}")
    student_answer = body.student_answer.strip()
    if not student_answer:
        raise HTTPException(status_code=400, detail="student_answer cannot be empty.")
    if len(body.student_answer) > MAX_ANSWER_CHARS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Answer is too long ({len(body.student_answer)} chars). "
                f"Maximum is {MAX_ANSWER_CHARS} characters."
            ),
        )

    # 3. Reconstruct state from DB
    examiner_messages   = json.loads(session.examiner_messages)
    picker_state        = json.loads(session.picker_state)
    transcript          = json.loads(session.transcript)
    pending_tool_use_id = session.pending_tool_use_id
    turn                = session.turn + 1   # the NEXT question number (e.g. 2 when answering Q1)
    examiner_temp       = session.examiner_temp
    # Snapshot reask state BEFORE calling examiner — used for injection and safety check
    is_reask_attempt    = bool(session.reask_pending)

    session_question_pool, _ = _get_assignment_resources(session.assignment_name or "test-assignment")
    picker = QuestionPicker.from_state(session_question_pool, picker_state, silent=True)

    # 4. Log student answer to transcript
    student_entry: dict = {
        "role": "Student",
        "answer_submitted_at": datetime.utcnow().isoformat(timespec="seconds"),
        "content": student_answer,
    }
    transcript.append(student_entry)

    # Peek 6 topic options (2 per difficulty) for the next question (without marking any as used yet)
    topic_options = picker.peek_options(["easy", "easy", "medium", "medium", "hard", "hard"])

    _OPTION_LABELS = ["easy-1", "easy-2", "medium-1", "medium-2", "hard-1", "hard-2"]
    print(f"[Picker] Q{turn} options offered to examiner:")
    for label, opt in zip(_OPTION_LABELS, topic_options):
        if opt is not None:
            print(f"  [{label}] {opt['files']} / {opt['focus'][:55]} ({opt['difficulty']})")
        else:
            print(f"  [{label}] (not available)")

    # 5. Call examiner
    client = _get_anthropic_client()
    _lang = (session.language or "he").lower()
    
    if session.assignment_name == "austin-a":
        _examiner_prompt = _read_file(os.path.join(_BACKEND_DIR, "prompts", "examiner_prompt_ut.txt"))
    else:
        _examiner_prompt = _examiner_prompt_for_language(EXAMINER_PROMPT, _lang)    
        
    # Un-indented to ensure it runs for all assignments
    examiner_messages, tool_use_id, examiner_json, model_used = call_examiner_qn(
        client,
        _examiner_prompt,
        examiner_messages,
        pending_tool_use_id,
        student_answer,
        topic_options,
        turn,
        picker,
        examiner_temp,
        switch_used=session.switch_used,
        reask_pending=is_reask_attempt,
    )

    action          = examiner_json.get("action", "NONE")
    question_text   = examiner_json.get("questionText", "")
    question_number = max(1, min(examiner_json.get("questionNumber", turn), 3))
    switch_granted  = examiner_json.get("switchGranted", False)
    action_params   = examiner_json.get("actionParameters") or {}
    action_file     = _resolve_action_file(action_params.get("fileName"), session.assignment_name or "test-assignment")
    action_code_line = action_params.get("codeLine")

    print(
        f"[session:turn] sid={body.session_id} github={session.github_username!r} turn={turn}"
        f" action={action!r} model={model_used!r}"
        f" score={examiner_json.get('understandingScore')} difficulty={examiner_json.get('chosenTopicDifficulty')!r}"
        f" authorship={examiner_json.get('authorshipConfidence')!r}"
    )

    # Safety: if reask was already pending and examiner returns RE_ASK again, override.
    # This prevents infinite re-ask loops if the examiner ignores the RE_ASK STATUS block.
    if is_reask_attempt and action == "RE_ASK":
        action = "NONE"

    # Clear reask state (re-set below only if a new RE_ASK is issued this turn)
    session.reask_pending = False

    # If examiner granted a switch, mark it on session
    if switch_granted:
        session.switch_used = True

    # 6. Handle FINISH_EXAM
    if action == "FINISH_EXAM":
        transcript.append({
            "role": "Examiner",
            "model": model_used,
            "question_shown_at": datetime.utcnow().isoformat(timespec="seconds"),
            "chosen_topic": None,
            "offered_topic_options": None,
            "content": examiner_json,
        })

        session.transcript        = json.dumps(transcript, ensure_ascii=False)
        session.examiner_messages = json.dumps(serialize_messages(examiner_messages), ensure_ascii=False)
        session.status            = "completed"
        db.commit()

        # Trigger asynchronous grading
        background_tasks.add_task(run_grader_background, session.session_id)

        return AnswerResponse(
            finished = True,
            message  = (
                "The exam has concluded. "
                "Your transcript is being evaluated — results will be available shortly."
            ),
        )

    # 6b. Handle END_EXAM_DISTRESS — terminate session, notify TA, no grading
    if action == "END_EXAM_DISTRESS":
        # Idempotency guard: if the session already ended via distress, do nothing further.
        # (Reload from DB to get the freshest status, not the cached object.)
        db.refresh(session)
        if session.status == "ended_distress":
            return AnswerResponse(
                finished      = True,
                distress_ended = True,
                question_text  = question_text,
            )

        # Persist the examiner's compassionate closing message as the last transcript entry.
        transcript.append({
            "role": "Examiner",
            "model": model_used,
            "question_shown_at": datetime.utcnow().isoformat(timespec="seconds"),
            "chosen_topic": None,
            "offered_topic_options": None,
            "distress_end": True,
            "content": examiner_json,
        })

        session.transcript          = json.dumps(transcript, ensure_ascii=False)
        session.examiner_messages   = json.dumps(serialize_messages(examiner_messages), ensure_ascii=False)
        session.status              = "ended_distress"
        db.commit()

        timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        # Pull the student message that triggered the signal (last student entry in transcript).
        trigger_message = ""
        for entry in reversed(transcript):
            if entry.get("role") == "Student":
                trigger_message = entry.get("content", "")
                break

        # ── Log to GCS ─────────────────────────────────────────────────────────
        distress_record = {
            "session_id":       session.session_id,
            "github_username":  session.github_username,
            "assignment_name":  session.assignment_name or "",
            "timestamp":     timestamp,
            "trigger_message": trigger_message,
            "question_number": question_number,
            "transcript_snapshot": transcript,
        }
        try:
            from github_stub import _gcs_client
            bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
            if bucket_name:
                bucket = _gcs_client.bucket(bucket_name)
                blob = bucket.blob(f"distress_events/{session.session_id}.json")
                # Only write if the blob doesn't already exist (idempotency).
                if not blob.exists():
                    blob.upload_from_string(
                        json.dumps(distress_record, ensure_ascii=False, indent=2),
                        content_type="application/json; charset=utf-8",
                    )
                    print(f"[Distress] Saved to GCS: distress_events/{session.session_id}.json")
                else:
                    print(f"[Distress] GCS entry already exists — skipping write for session {session.session_id}.")
            else:
                print(f"[Distress] GCS_SUBMISSIONS_BUCKET not set — distress event logged locally only.")
        except Exception as e:
            print(f"[Distress] GCS save failed: {e}")

        print(f"[Distress] {json.dumps(distress_record, ensure_ascii=False)}")

        # ── Notify TA via email ─────────────────────────────────────────────────
        _send_distress_email(
            session_id      = session.session_id,
            github_username = session.github_username,
            assignment_name = session.assignment_name or "",
            trigger_message = trigger_message,
            question_number = question_number,
            timestamp       = timestamp,
        )

        return AnswerResponse(
            finished       = True,
            distress_ended = True,
            question_text  = question_text,
        )

    # 6c. Handle RE_ASK — stay on the same question, no topic marked, no turn advance
    if action == "RE_ASK":
        # Tag the student's weird answer in the transcript so the grader can see it
        student_entry["reask_triggered"] = True

        transcript.append({
            "role": "Examiner",
            "model": model_used,
            "question_shown_at": datetime.utcnow().isoformat(timespec="seconds"),
            "chosen_topic": None,
            "offered_topic_options": None,
            "reask": True,
            "content": examiner_json,
        })

        session.transcript          = json.dumps(transcript, ensure_ascii=False)
        session.examiner_messages   = json.dumps(serialize_messages(examiner_messages), ensure_ascii=False)
        session.pending_tool_use_id = tool_use_id
        session.reask_pending       = True
        # session.turn intentionally NOT updated — student stays on the same question
        db.commit()

        return AnswerResponse(
            finished        = False,
            question_text   = question_text,
            question_number = question_number,
        )

    # 7. Register the topic the examiner chose
    chosen_label = examiner_json.get("chosenTopicLabel")
    _label_to_idx = {"easy-1": 0, "easy-2": 1, "medium-1": 2, "medium-2": 3, "hard-1": 4, "hard-2": 5}
    if chosen_label and chosen_label in _label_to_idx:
        chosen_idx = _label_to_idx[chosen_label]
    else:
        # Fallback: derive from chosenTopicDifficulty (maps to first option of that difficulty)
        chosen_diff = examiner_json.get("chosenTopicDifficulty", "medium")
        chosen_idx  = {"easy": 0, "medium": 2, "hard": 4}.get(chosen_diff, 2)
    chosen_topic = topic_options[chosen_idx] if chosen_idx < len(topic_options) and topic_options[chosen_idx] is not None \
                   else next((o for o in topic_options if o is not None), None)

    if chosen_topic is not None:
        picker.mark_used(chosen_topic)

    # If the examiner granted a switch, tag the student entry with the switch metadata
    # so the grader can recover the original question text and the student's exact words.
    if switch_granted:
        student_entry["switch_event"]       = True
        student_entry["switch_at_question"] = question_number  # replacement question number

    # Log examiner turn
    transcript.append({
        "role": "Examiner",
        "model": model_used,
        "question_shown_at": datetime.utcnow().isoformat(timespec="seconds"),
        "chosen_topic": chosen_topic,
        "offered_topic_options": [
            picker.format_topic_for_examiner(o) for o in topic_options if o is not None
        ],
        "switch_replacement": switch_granted,
        "content": examiner_json,
    })

    # Persist updated state
    session.transcript          = json.dumps(transcript, ensure_ascii=False)
    session.examiner_messages   = json.dumps(serialize_messages(examiner_messages), ensure_ascii=False)
    session.picker_state        = json.dumps(picker.to_state(), ensure_ascii=False)
    session.pending_tool_use_id = tool_use_id
    # Only advance the turn counter when no switch was granted.
    # A switch means the student stays on the same question number — session.turn stays put,
    # so the next call computes the same `turn` value and processes the replacement answer.
    if not switch_granted:
        session.turn = turn
    db.commit()

    internal_eval      = examiner_json.get("internalEvaluation", {}) or {}
    if isinstance(internal_eval, str):
        try:
            internal_eval = json.loads(internal_eval)
        except Exception:
            internal_eval = {}

    internal_reasoning = examiner_json.get("internalReasoning", {}) or {}
    if isinstance(internal_reasoning, str):
        try:
            internal_reasoning = json.loads(internal_reasoning)
        except Exception:
            internal_reasoning = {}

    return AnswerResponse(
        finished               = False,
        question_text          = question_text,
        question_number        = question_number,
        chosen_difficulty      = examiner_json.get("chosenTopicDifficulty"),
        next_difficulty_signal = examiner_json.get("nextQuestionDifficulty"),
        understanding_score    = internal_eval.get("understandingScore"),
        authorship_confidence  = internal_eval.get("authorshipConfidence"),
        internal_reasoning     = internal_reasoning.get("adaptiveDifficultyStrategy"),
        offered_topics         = [
            picker.format_topic_for_examiner(o) for o in topic_options if o is not None
        ],
        switch_granted         = switch_granted if switch_granted else None,
        action                 = action,
        action_file            = action_file,
        action_code_line       = action_code_line,
    )


def _build_timeout_metadata(
    timed_out_at_question: int,
    partial_captured: bool,
    total_questions: int = 3,
) -> dict:
    """
    Build the timeout_metadata dict with mutually-exclusive question buckets.

    Each question lands in exactly one of:
      questions_answered   — student has answer text (normal submit or timeout-captured)
      questions_not_reached — no answer text at all

    questions_partial is a sub-list of questions_answered identifying answers that
    were captured by the timer rather than submitted by the student.

    session.turn == timed_out_at_question because the examiner sets it when it asks
    a question; RE_ASK and switch do not advance the turn counter, so it always
    equals the current question number — independent of how many Student transcript
    entries exist.
    """
    if partial_captured:
        # The timed-out question has captured text — it is answered (partially)
        questions_answered  = list(range(1, timed_out_at_question + 1))
        questions_partial   = [timed_out_at_question]
        questions_not_reached = list(range(timed_out_at_question + 1, total_questions + 1))
    else:
        # No text was captured — the timed-out question was never answered
        questions_answered  = list(range(1, timed_out_at_question))
        questions_partial   = []
        questions_not_reached = list(range(timed_out_at_question, total_questions + 1))

    return {
        "timed_out_at_question":  timed_out_at_question,
        "questions_answered":     questions_answered,
        "questions_partial":      questions_partial,
        "questions_not_reached":  questions_not_reached,
        "partial_answer_captured": partial_captured,
    }


# ---------------------------------------------------------------------------
# POST /api/exam/timeout
# ---------------------------------------------------------------------------

@app.post("/api/exam/timeout", response_model=TimeoutResponse)
def exam_timeout(
    body: TimeoutRequest,
    background_tasks: BackgroundTasks,
    db: DBSession = Depends(get_db),
) -> TimeoutResponse:
    """
    Called by the frontend when the exam timer expires.

    Marks the session as timed out, records which questions were answered
    vs. never reached, then triggers the same background grading pipeline
    as a normal FINISH_EXAM.
    """
    session = db.query(ExamSession).filter(ExamSession.session_id == body.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.status != "in-progress":
        raise HTTPException(
            status_code=400,
            detail=f"Session is already '{session.status}'. Cannot time out."
        )

    print(f"[session:timeout] sid={body.session_id} github={session.github_username!r} turn={session.turn}")
    transcript = json.loads(session.transcript)

    # If the student had typed a partial answer, append it so the grader can evaluate it
    partial_captured = False
    if body.partial_answer and body.partial_answer.strip():
        transcript.append({
            "role": "Student",
            "answer_submitted_at": datetime.utcnow().isoformat(timespec="seconds"),
            "content": body.partial_answer.strip(),
            "timeout_partial": True,
        })
        partial_captured = True
        print(f"[session:timeout] partial answer captured ({len(body.partial_answer.strip())} chars)")

    # session.turn is the question number the examiner last asked (the one the student
    # was on when the timer fired). Base all categorisation on that, not on counting
    # Student turns — RE_ASK and switch events add extra Student turns and would overcount.
    timed_out_at_question = session.turn
    meta = _build_timeout_metadata(timed_out_at_question, partial_captured)

    # Persist timeout state
    session.timed_out = True
    session.timeout_metadata = json.dumps(meta, ensure_ascii=False)
    session.transcript = json.dumps(transcript, ensure_ascii=False)
    session.status = "completed"
    db.commit()

    # Trigger background grading (same path as FINISH_EXAM)
    background_tasks.add_task(run_grader_background, session.session_id)

    return TimeoutResponse(
        status              = "saved",
        questions_answered  = len(meta["questions_answered"]),
        questions_timed_out = len(meta["questions_not_reached"]),
    )


# ---------------------------------------------------------------------------
# POST /api/admin/invalidate-session
# ---------------------------------------------------------------------------

@app.post("/api/admin/invalidate-session", response_model=InvalidateSessionResponse)
def invalidate_session(
    body: InvalidateSessionRequest,
    db: DBSession = Depends(get_db),
) -> InvalidateSessionResponse:
    """
    Admin-only: set session(s) to a status that lets the student retake the exam.
    Session data is preserved for audit purposes — nothing is deleted.

    new_status (default "retake_enabled"):
      - "retake_enabled" — the sitting was fine; just allow another attempt.
      - "invalidated"    — the exam didn't go through. The sitting is discarded:
                           hidden from the dashboard/exports, grade never emailed.

    Usage:
      - Pass session_id to act on a specific session.
      - Pass github_username + assignment_name to act on all sessions for that pair.
    """
    if not body.session_id and not (body.github_username and body.assignment_name):
        raise HTTPException(
            status_code=400,
            detail="Provide either 'session_id' or both 'github_username' and 'assignment_name'.",
        )

    if body.session_id:
        session = db.query(ExamSession).filter(ExamSession.session_id == body.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"Session '{body.session_id}' not found.")
        sessions = [session]
    else:
        sessions = (
            db.query(ExamSession)
            .filter(
                func.lower(ExamSession.github_username) == (body.github_username or "").strip().lower(),
                ExamSession.assignment_name == body.assignment_name,
            )
            .all()
        )
        if not sessions:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No sessions found for '{body.github_username}' "
                    f"on assignment '{body.assignment_name}'."
                ),
            )

    new_status = body.new_status
    if new_status not in RETAKE_UNLOCKING_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"new_status must be one of {list(RETAKE_UNLOCKING_STATUSES)}.",
        )

    invalidated_ids = []
    for s in sessions:
        print(
            f"[Admin] Session {s.session_id} → {new_status} "
            f"(was '{s.status}', github={s.github_username}, reason={body.reason!r})"
        )
        s.status = new_status
        invalidated_ids.append(s.session_id)

        # Stamp the GCS result blob so blob-based views also hide this session
        if s.github_username and s.assignment_name:
            try:
                bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
                if bucket_name:
                    from github_stub import _gcs_client
                    blob_path = f"results/{s.assignment_name}/{s.github_username}.json"
                    blob = _gcs_client.bucket(bucket_name).blob(blob_path)
                    existing = json.loads(blob.download_as_text())
                    existing["status"] = new_status
                    blob.upload_from_string(
                        json.dumps(existing, ensure_ascii=False, indent=2),
                        content_type="application/json; charset=utf-8",
                    )
                    print(f"[Admin] Blob {blob_path} stamped as {new_status}.")
            except Exception as exc:
                print(f"[Admin] Warning: could not stamp blob for {s.github_username}: {exc}")

    db.commit()

    return InvalidateSessionResponse(
        invalidated_sessions = invalidated_ids,
        github_username      = body.github_username or sessions[0].github_username,
        reason               = body.reason,
    )


# ---------------------------------------------------------------------------
# POST /api/exam/complaint
# ---------------------------------------------------------------------------

def _send_complaint_email(
    session_id: str,
    github_username: str,
    assignment_name: str,
    contact_name: str,
    contact_info: str,
    note: str,
    timestamp: str,
) -> None:
    """
    Send a complaint notification email to the TA.
    Requires env vars: SMTP_USER, SMTP_PASSWORD, and optionally SMTP_HOST / SMTP_PORT / TA_EMAIL.
    Silently skips if SMTP_USER is not configured.
    """
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    if not smtp_user or not smtp_password:
        print(f"[Complaint] SMTP not configured — skipping email for session {session_id}.")
        return

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    ta_email  = os.environ.get("TA_EMAIL", "Shachar.sagi@biu.ac.il")

    subject = f"פנייה מסטודנט — {github_username} | {assignment_name}"
    body = (
        f"פנייה חדשה התקבלה במערכת הערכת הידע.\n\n"
        f"פרטי הסטודנט:\n"
        f"  שם משתמש GitHub: {github_username}\n"
        f"  מטלה: {assignment_name}\n"
        f"  מזהה סשן: {session_id}\n\n"
        f"פרטי קשר שהסטודנט השאיר:\n"
        f"  שם: {contact_name}\n"
        f"  פרטי קשר: {contact_info}\n"
        f"  הערה: {note or '(ללא)'}\n\n"
        f"תאריך ושעה: {timestamp}\n\n"
        f"לבדיקת הסשן: GET /api/admin/results/{github_username}\n"
        f"קובץ התלונה נשמר ב-GCS תחת complaints/{session_id}.json\n"
    )

    # CC the student if contact_info looks like a valid email
    student_email = contact_info.strip() if _re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", contact_info.strip()) else None
    recipients = [ta_email] + ([student_email] if student_email else [])

    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = ta_email
    if student_email:
        msg["CC"] = student_email

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipients, msg.as_string())
        print(f"[Complaint] Email sent to {recipients} for session {session_id}.")
    except Exception as e:
        print(f"[Complaint] Failed to send email: {e}")


def _send_distress_email(
    session_id: str,
    github_username: str,
    assignment_name: str,
    trigger_message: str,
    question_number: int,
    timestamp: str,
) -> None:
    """
    Send a TA notification email when an END_EXAM_DISTRESS event is detected.
    Reuses the same SMTP configuration as the complaint flow.
    Silently skips if SMTP_USER is not configured.
    """
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    if not smtp_user or not smtp_password:
        print(f"[Distress] SMTP not configured — skipping email for session {session_id}.")
        return

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    ta_email  = os.environ.get("TA_EMAIL", "Shachar.sagi@biu.ac.il")

    subject = DISTRESS_EMAIL_SUBJECT.format(session_id=session_id)
    body = DISTRESS_EMAIL_BODY.format(
        github_username = github_username,
        assignment_name = assignment_name,
        session_id      = session_id,
        timestamp       = timestamp,
        question_number = question_number,
        trigger_message = trigger_message,
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = ta_email

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, ta_email, msg.as_string())
        print(f"[Distress] Email sent to {ta_email} for session {session_id}.")
    except Exception as e:
        print(f"[Distress] Failed to send email: {e}")


@app.post("/api/exam/complaint", response_model=ComplaintResponse)
def submit_complaint(
    body: ComplaintRequest,
    db: DBSession = Depends(get_db),
) -> ComplaintResponse:
    """
    Record a student complaint. Accepts pre-exam complaints (no session yet)
    via github_username, or mid-exam complaints via session_id.

    Saves a JSON record to GCS at complaints/{session_id}.json and sends
    an email to the TA.
    """
    session = None
    if body.session_id:
        session = db.query(ExamSession).filter(ExamSession.session_id == body.session_id).first()

    complaint_id     = body.session_id or f"pre-exam:{body.github_username or 'unknown'}"
    github_username  = (session.github_username if session else body.github_username) or "unknown"
    assignment_name  = (session.assignment_name if session else "") or ""
    session_status   = session.status if session else "pre-exam"
    timestamp        = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Mark session as complaint_pending so the student cannot start a new session
    # until faculty manually reviews and invalidates via the admin endpoint.
    if session and session.status not in ("graded", "invalidated", "complaint_pending"):
        session.status = "complaint_pending"
        db.commit()
        print(f"[Complaint] Session {session.session_id} marked complaint_pending.")

    complaint_record = {
        "session_id":    complaint_id,
        "github_username": github_username,
        "assignment_name": assignment_name,
        "contact_name":  body.contact_name,
        "contact_info":  body.contact_info,
        "note":          body.note or "",
        "timestamp":     timestamp,
        "session_status_at_complaint": session_status,
    }

    # ── Save to GCS ──────────────────────────────────────────────────────────
    try:
        from github_stub import _gcs_client
        bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
        if bucket_name:
            bucket = _gcs_client.bucket(bucket_name)
            blob = bucket.blob(f"complaints/{complaint_id}.json")
            blob.upload_from_string(
                json.dumps(complaint_record, ensure_ascii=False, indent=2),
                content_type="application/json; charset=utf-8",
            )
            print(f"[Complaint] Saved to GCS: complaints/{complaint_id}.json")
        else:
            print(f"[Complaint] GCS_SUBMISSIONS_BUCKET not set — complaint logged only.")
    except Exception as e:
        print(f"[Complaint] GCS save failed: {e}")
        # Don't fail the request — still try to send email and return success.

    print(f"[Complaint] {json.dumps(complaint_record, ensure_ascii=False)}")

    # ── Send email ────────────────────────────────────────────────────────────
    _send_complaint_email(
        session_id      = complaint_id,
        github_username = github_username,
        assignment_name = assignment_name,
        contact_name    = body.contact_name,
        contact_info    = body.contact_info,
        note            = body.note or "",
        timestamp       = timestamp,
    )

    return ComplaintResponse(status="recorded", session_id=complaint_id)


# ---------------------------------------------------------------------------
# POST /api/exam/preview
# ---------------------------------------------------------------------------

@app.post("/api/exam/preview", response_model=PreviewResponse)
def exam_preview(body: PreviewRequest) -> PreviewResponse:
    """
    Return the student's submitted files for preview at the confirm screen,
    without creating a session.  Calls GitHub if the files are not yet cached.
    """
    github_username = body.github_username.strip()
    assignment_name = (body.assignment_name or os.environ.get("ASSIGNMENT_NAME", "test-assignment")).strip()

    is_qa = assignment_name in QA_ASSIGNMENTS
    if not is_qa:
        try:
            fetch_and_save_submission(github_username, assignment_name)
        except Exception:
            pass  # best-effort — return whatever is cached

    files = load_local_submission(github_username, assignment_name)
    try:
        _, assignment_readme = _get_assignment_resources(assignment_name)
        if assignment_readme:
            files = {"README.md": assignment_readme, **files}
    except HTTPException:
        pass  # assignment not on this server — skip README in preview
    return PreviewResponse(files=files, fetched=bool(files))


# ---------------------------------------------------------------------------
# GET /api/exam/lookup/{github_username}
# ---------------------------------------------------------------------------

@app.get("/api/exam/lookup/{github_username}", response_model=LookupResponse)
def lookup_github(
    github_username: str,
    assignment_name: Optional[str] = None,  # explicit override (student switched)
    db: DBSession = Depends(get_db),
) -> LookupResponse:
    """
    Detect which assignment a student should take, verify they have a submission,
    and check the one-time-use lock.

    Assignment resolution order:
      1. `assignment_name` query param (student explicitly switched on the confirm screen)
      2. `_assignment_map` (loaded from private/required_students_*.json on GCS)
      3. DEFAULT_ASSIGNMENT fallback
    """
    github_username = github_username.strip()
    assignment_name = "austin-a"

    # Did the student explicitly pick this assignment (switched on the confirm
    # screen), or is this the auto-routed default? A locked *default* must not be a
    # dead end — see the lock block below.
    explicit_choice = bool(assignment_name and assignment_name.strip())

    # ── Determine assignment ───────────────────────────────────────────────────
    if assignment_name:
        assignment_name = assignment_name.strip()
    else:
        full_id = _resolve_github_to_full_id(github_username)
        base_assignment = (
            (_assignment_map.get(full_id) if full_id else None)
            or DEFAULT_ASSIGNMENT
        )
        # Graded-gated default: every student must take LATEST_ASSIGNMENT, but
        # only after they've completed (graded) their required earlier one. Until
        # then default to that earlier assignment so they finish it first. The
        # latest assignment stays selectable for everyone on the confirm screen.
        assignment_name = base_assignment
        if base_assignment != LATEST_ASSIGNMENT:
            has_graded_base = (
                db.query(ExamSession)
                .filter(
                    ExamSession.github_username == github_username,
                    ExamSession.assignment_name == base_assignment,
                    ExamSession.status == "graded",
                )
                .first()
                is not None
            )
            if has_graded_base:
                assignment_name = LATEST_ASSIGNMENT

    labels = ASSIGNMENT_LABELS.get(assignment_name, {})
    label_he = labels.get("he", assignment_name)
    label_en = labels.get("en", assignment_name)

    # All switchable options shown on the confirm screen
    available = [
        AssignmentOption(
            name=a,
            label_he=ASSIGNMENT_LABELS.get(a, {}).get("he", a),
            label_en=ASSIGNMENT_LABELS.get(a, {}).get("en", a),
        )
        for a in KNOWN_ASSIGNMENTS
    ]

    is_qa = assignment_name in QA_ASSIGNMENTS or assignment_name == "austin-a"
    if not is_qa:
        try:
            fetch_result = fetch_and_save_submission(github_username, assignment_name)
        except Exception as exc:
            return LookupResponse(found=False, locked=False, github_username=github_username,
                                  assignment_name=assignment_name, error=str(exc))
        if not fetch_result.files_saved:
            # Fallback: try the other known assignments in case the student is in a different group
            fallback_result = None
            fallback_assignment = None
            for alt in KNOWN_ASSIGNMENTS:
                if alt == assignment_name:
                    continue
                try:
                    r = fetch_and_save_submission(github_username, alt)
                    if r.files_saved:
                        fallback_result = r
                        fallback_assignment = alt
                        break
                except Exception:
                    continue
            if fallback_assignment:
                assignment_name = fallback_assignment
                labels = ASSIGNMENT_LABELS.get(assignment_name, {})
                label_he = labels.get("he", assignment_name)
                label_en = labels.get("en", assignment_name)
                fetch_result = fallback_result
            else:
                return LookupResponse(found=False, locked=False, github_username=github_username,
                                      assignment_name=assignment_name,
                                      error=f"No submission files found for '{github_username}' in the GitHub Classroom repository.")

        # One-time-use lock (test identities in config.UNLIMITED_RETAKE_IDS are exempt —
        # must match the exemption in /api/auth/start, or lookup blocks a retake that start
        # would have allowed and the student is stuck on the entry screen).
        existing = None if is_unlimited_retake(github_username) else (
            db.query(ExamSession)
            .filter(
                ExamSession.github_username == github_username,
                ExamSession.assignment_name == assignment_name,
                ExamSession.status.notin_(RETAKE_UNLOCKING_STATUSES),
            )
            .first()
        )
        if existing:
            lock_reason = "complaint_pending" if existing.status == "complaint_pending" else "already_started"
            # A genuine hold (complaint_pending) always stops here. An
            # already-used lock stops only when the student *explicitly* chose this
            # assignment. On the auto-routed default it must NOT be terminal: a
            # student who completed the latest assignment is auto-routed to it, and
            # bouncing them to the entry screen hid the assignment switcher — so an
            # admin-cleared retake of an earlier assignment was unreachable (the
            # student could never get past the locked default to switch down). Fall
            # through to the confirm screen instead; start_exam still enforces the
            # one-time lock if they actually try to start a locked assignment.
            if lock_reason == "complaint_pending" or explicit_choice:
                return LookupResponse(
                    found=True, locked=True,
                    github_username=github_username,
                    assignment_name=assignment_name,
                    assignment_label_he=label_he,
                    assignment_label_en=label_en,
                    error=lock_reason,
                )

    return LookupResponse(
        found=True, locked=False,
        github_username=github_username,
        assignment_name=assignment_name,
        assignment_label_he=label_he,
        assignment_label_en=label_en,
        available_assignments=available,
    )


# ---------------------------------------------------------------------------
# POST /api/admin/invalidate/{github_username}
# ---------------------------------------------------------------------------

@app.post("/api/admin/invalidate/{github_username}")
def invalidate_by_github(github_username: str, db: DBSession = Depends(get_db)):
    """
    Admin: clear all sessions for a github_username so they can retake the exam.
    Call this when a student had a technical failure and needs to re-enter.
    Sessions are marked 'invalidated' — data is preserved for audit.
    """
    assignment_name = os.environ.get("ASSIGNMENT_NAME", "test-assignment").strip()
    sessions = (
        db.query(ExamSession)
        .filter(
            func.lower(ExamSession.github_username) == github_username.strip().lower(),
            ExamSession.assignment_name == assignment_name,
        )
        .all()
    )
    for s in sessions:
        print(f"[Admin] Invalidating session {s.session_id} for github={github_username!r}")
        s.status = "invalidated"
    db.commit()
    return {"invalidated": len(sessions), "github_username": github_username, "assignment_name": assignment_name}


# ---------------------------------------------------------------------------
# POST /api/admin/reload-id-map
# ---------------------------------------------------------------------------

@app.post("/api/admin/reload-id-map")
def reload_id_map(request: Request) -> dict:
    """Reload id_mapping.csv from GCS. Auth: X-Admin-Key header."""
    _require_admin(request)
    return _load_id_mapping()


@app.post("/api/admin/reload-username-fallback-map")
def reload_username_fallback_map(request: Request) -> dict:
    """Reload github_username_fallback_ids.csv from GCS. Auth: X-Admin-Key header."""
    _require_admin(request)
    loaded = _load_username_fallback_map()
    return {"loaded": loaded}


# ---------------------------------------------------------------------------
# Admin viewer auth dependency
# ---------------------------------------------------------------------------

def _require_admin(request: Request) -> None:
    """Check X-Admin-Key header against VIEWER_PASSWORD env var."""
    password = os.environ.get("VIEWER_PASSWORD", "").strip()
    if not password:
        raise HTTPException(status_code=503, detail="VIEWER_PASSWORD not configured on server.")
    key = request.headers.get("X-Admin-Key", "")
    if not key or key != password:
        raise HTTPException(status_code=401, detail="Unauthorized. Provide correct X-Admin-Key header.")


def _require_known_assignment(assignment: str) -> str:
    """Reject an assignment this deployment does not serve.

    Storage is shared across courses — one bucket, one database — so an admin endpoint that
    takes an assignment name will happily read another course's data if simply handed its
    name. KNOWN_ASSIGNMENTS is narrowed by COURSE_ID, so checking against it confines each
    course's admin to its own students. Authentication is per course, so without this the
    Linear Algebra password would read Operating Systems results.
    """
    name = (assignment or "").strip()
    if name not in KNOWN_ASSIGNMENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown assignment {name!r} for this deployment. "
                   f"Available: {sorted(KNOWN_ASSIGNMENTS)}")
    return name


# ---------------------------------------------------------------------------
# Admin viewer helpers
# ---------------------------------------------------------------------------

_DEBUG_BLOB_FIELDS = {"examiner_messages", "picker_state", "session_seed", "examiner_temp"}


def _parse_utc_dt(s: str) -> Optional[datetime]:
    """
    Parse an ISO datetime string to a UTC-aware datetime.
    - RFC3339 with offset (e.g. "2025-05-14T10:00:00+03:00") → parsed as-is
    - "Z" suffix → treated as UTC
    - No timezone indicator → treated as UTC (our stored values use datetime.utcnow())
    """
    if not s:
        return None
    s2 = s.strip()
    if s2.endswith("Z"):
        s2 = s2[:-1] + "+00:00"
    elif not _re.search(r"[+-]\d{2}:?\d{2}$", s2):
        s2 += "+00:00"
    try:
        return datetime.fromisoformat(s2)
    except Exception:
        return None


def _student_summary(r: dict) -> dict:
    fg = r.get("final_grade") or {}
    gv = r.get("grader_verdict") or {}

    session_minutes = None
    start_t = _parse_utc_dt(r.get("start_time") or "")
    tdata = r.get("transcript")
    if start_t and isinstance(tdata, list) and tdata:
        for entry in reversed(tdata):
            ts_str = entry.get("question_shown_at") or entry.get("answer_submitted_at")
            if ts_str:
                last_ts = _parse_utc_dt(ts_str)
                if last_ts:
                    dur = (last_ts - start_t).total_seconds()
                    if 60 <= dur <= 7200:
                        session_minutes = round(dur / 60, 1)
                break

    return {
        "github_username":       r.get("github_username"),
        "student_id":            r.get("student_id"),
        "hebrew_name":           r.get("hebrew_name"),
        "final_grade":           fg.get("finalWeightedGrade"),
        "oral_score":            fg.get("oralDefenseScore"),
        "code_score":            fg.get("staticCodeQualityScore"),
        "authorship_assessment": gv.get("authorshipAssessment"),
        "integrity_flag":        gv.get("integrityFlag"),
        "prompt_injection_flag": gv.get("promptInjectionFlag"),
        "id_resolution_status":  r.get("id_resolution_status"),
        "timed_out":             r.get("timed_out"),
        "switch_used":           r.get("switch_used"),
        "exam_start_time":       r.get("start_time"),
        "session_minutes":       session_minutes,
    }


def _get_admin_bucket():
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        raise HTTPException(status_code=503, detail="GCS_SUBMISSIONS_BUCKET not configured.")
    from github_stub import _gcs_client
    return _gcs_client.bucket(bucket_name)


def _load_assignment_blobs(assignment: str) -> tuple[list[dict], set[str]]:
    """Download all result blobs for an assignment.

    Returns (records, invalidated_usernames) where records excludes invalidated
    sessions and invalidated_usernames is the set of github_usernames whose
    latest blob is stamped invalidated.
    """
    bucket = _get_admin_bucket()
    prefix = f"results/{assignment}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    records: list[dict] = []
    invalidated_usernames: set[str] = set()
    for blob in blobs:
        if not blob.name.endswith(".json"):
            continue
        try:
            record = json.loads(blob.download_as_text())
            # Drop the heavy debug fields before holding the record in memory.
            # examiner_messages alone is ~70% of each blob; with the admin cache
            # keeping every assignment's records resident, loading them whole is what
            # OOM'd the instances. No admin view reads them (they're in
            # _DEBUG_BLOB_FIELDS and stripped from responses), so dropping them here
            # cuts dashboard memory ~70% and lets it scale to the full cohort.
            record.pop("examiner_messages", None)
            record.pop("picker_state", None)
            if record.get("status") == "invalidated":
                uname = record.get("github_username", "")
                if uname:
                    invalidated_usernames.add(uname)
                continue
            records.append(record)
        except Exception as exc:
            print(f"[Admin] Could not parse blob {blob.name}: {exc}")
    return records, invalidated_usernames


# ---------------------------------------------------------------------------
# GET /api/admin/results/assignments
# ---------------------------------------------------------------------------

@app.get("/api/admin/results/assignments")
def admin_list_assignments(
    github_username: Optional[str] = Query(None, description="Filter to one student's result blobs"),
    _: None = Depends(_require_admin),
) -> dict:
    """
    Assignment names that have viewable result blobs, restricted to this deployment's course.
    With github_username: only assignments that have a blob for that student.

    Driven by KNOWN_ASSIGNMENTS rather than by whatever prefixes exist under results/, which
    fixes two faults of the previous scan. The bucket is shared by every course, so listing
    its prefixes offered Operating Systems assignments in the Linear Algebra admin. And a
    namespaced assignment ("linear-algebra/hw1") occupies two path segments, so a
    single-level prefix scan reported the course name, "linear-algebra" — a value no session
    is stored under, which made every downstream stats query silently return nothing.
    """
    bucket = _get_admin_bucket()
    assignments = []

    for name in KNOWN_ASSIGNMENTS:
        prefix = f"results/{name}/"
        if github_username:
            if bucket.blob(f"{prefix}{github_username}.json").exists():
                assignments.append(name)
        elif next(iter(bucket.list_blobs(prefix=prefix, max_results=1)), None) is not None:
            assignments.append(name)

    return {"assignments": sorted(assignments)}


# ---------------------------------------------------------------------------
# GET /api/admin/results/by-github/{username}
# ---------------------------------------------------------------------------

@app.get("/api/admin/results/by-github/{username}")
def admin_student_detail(
    username: str,
    assignment: str = Query(..., description="Assignment name"),
    _: None = Depends(_require_admin),
) -> dict:
    """
    Full result for one student (GCS blob minus debug fields).
    Re-runs name resolution with the live ID map (updated if CSV was reloaded).
    """
    assignment = _require_known_assignment(assignment)
    bucket = _get_admin_bucket()
    blob_path = f"results/{assignment}/{username}.json"
    try:
        data: dict = json.loads(bucket.blob(blob_path).download_as_text())
    except Exception:
        raise HTTPException(status_code=404, detail=f"No result blob found for '{username}' / '{assignment}'.")

    if data.get("status") == "invalidated":
        raise HTTPException(status_code=404, detail=f"Session for '{username}' / '{assignment}' has been invalidated.")

    # Strip internal debug fields
    for field in _DEBUG_BLOB_FIELDS:
        data.pop(field, None)

    # Re-resolve name with live id map (in case CSV was reloaded after grading)
    id_status = data.get("id_resolution_status")
    if id_status in ("ok_9_digits", "ok_5_digits"):
        resolved_fid, resolved_name, new_status = resolve_student_name(
            data.get("student_id"), data.get("full_id_from_repo"), id_status
        )
        data["full_id"]              = resolved_fid or data.get("full_id_from_repo")
        data["hebrew_name"]          = resolved_name
        data["id_resolution_status"] = new_status

    # Email readiness validation + preview
    from grade_email_template import validate_email_readiness, build_grade_email
    data["email_validation"] = validate_email_readiness(data)
    try:
        subject, body = build_grade_email(data)
        data["email_preview"] = {"subject": subject, "body": body}
    except Exception as exc:
        data["email_preview"] = {"error": str(exc)}

    return data


# ---------------------------------------------------------------------------
# GET /api/admin/results/email-status
# ---------------------------------------------------------------------------

@app.get("/api/admin/results/email-status")
def admin_email_status(
    assignment: str = Query(..., description="Assignment name"),
    _: None = Depends(_require_admin),
) -> dict:
    """
    Per-student email delivery status and readiness for an assignment.
    Shows who has been sent their grade, who is pending, and who has missing fields
    that would block sending (e.g. missing studentFeedback or studentStaticFeedback).
    """
    from grade_email_template import validate_email_readiness
    assignment = _require_known_assignment(assignment)
    records, _ = _load_assignment_blobs(assignment)
    records.sort(key=lambda r: r.get("github_username") or "")

    students = []
    for r in records:
        validation = validate_email_readiness(r)
        students.append({
            "github_username":  r.get("github_username"),
            "hebrew_name":      r.get("hebrew_name"),
            "full_id":          r.get("full_id") or r.get("full_id_from_repo"),
            "grade_email_sent": r.get("grade_email_sent"),
            "email_valid":      validation["is_valid"],
            "missing_fields":   validation["missing_fields"],
        })

    sent    = sum(1 for s in students if s["grade_email_sent"])
    invalid = sum(1 for s in students if not s["email_valid"])

    return {
        "assignment": assignment,
        "total":      len(students),
        "sent":       sent,
        "not_sent":   len(students) - sent,
        "invalid":    invalid,
        "students":   students,
    }


# ---------------------------------------------------------------------------
# GET /api/admin/stats/{assignment}
# ---------------------------------------------------------------------------

@app.get("/api/admin/stats/{assignment}")
def admin_assignment_stats(
    assignment: str,
    force: bool = False,
    background_tasks: BackgroundTasks = None,
    _: None = Depends(_require_admin),
) -> dict:
    """
    Per-assignment participation statistics:
      - Graded sessions (from DB result blobs)
      - Calendar slot registrations (Google Calendar)
      - Pre-survey form responses (Google Sheets)
      - Email sent status
      - Required students list (GCS private/required_students_{assignment}.json — optional)

    Some data sources may be unavailable (returns null with an error note).
    """
    assignment = _require_known_assignment(assignment)
    if not force:
        cached, _ = _cache_get(assignment, "stats")
        if cached is not None:
            if background_tasks is not None:
                background_tasks.add_task(_bg_refresh_stats, assignment)
            return cached

    from grade_email_template import validate_email_readiness

    # ── Graded sessions ───────────────────────────────────────────────────────
    records, invalidated_usernames = _load_assignment_blobs(assignment)
    email_sent_usernames = {r.get("github_username") for r in records if r.get("grade_email_sent")}

    # ── Required students list ────────────────────────────────────────────────
    required_ids: Optional[list] = None
    required_error: Optional[str] = None
    try:
        bucket = _get_admin_bucket()
        required_path = f"private/required_students_{assignment}.json"
        required_ids = json.loads(bucket.blob(required_path).download_as_text())
    except Exception as exc:
        required_error = str(exc)

    # ── Google Calendar registrations — REMOVED 2026-07 ───────────────────────
    # The course stopped using the Calendar sign-up cross-reference, and the Google Calendar
    # API call was the chronic source of this endpoint's 504 timeouts. We no longer fetch it;
    # all calendar_* fields stay empty and the cross-reference block below auto-skips (it is
    # guarded by `if calendar_events and records`). See MULTI_COURSE_MIGRATION §admin notes.
    calendar_emails:  Optional[set]       = None
    calendar_by_day:  Optional[dict]      = None
    calendar_by_hour: Optional[dict]      = None
    calendar_events:  Optional[list]      = None
    calendar_error:   Optional[str]       = None

    # ── Google Sheets pre-survey responses ────────────────────────────────────
    survey_ids: Optional[set] = None
    survey_error: Optional[str] = None
    survey_row_count: Optional[int] = None
    try:
        import google_apis
        headers, rows = google_apis._get_sheet_rows_for(google_apis.SURVEY_SHEET_ID)
        survey_row_count = len(rows)
        survey_ids = google_apis.extract_respondent_ids(headers, rows, "תעודת זהות")
        if survey_row_count > 0 and len(survey_ids) == 0:
            survey_error = f"0 IDs extracted from {survey_row_count} rows. Headers: {headers[:6]}"
    except Exception as exc:
        survey_error = str(exc)

    # ── Google Sheets post-survey responses (mandatory AI policy survey) ──────
    post_survey_ids: Optional[set] = None
    post_survey_error: Optional[str] = None
    try:
        import google_apis
        post_survey_ids = google_apis.get_post_survey_respondent_ids()
    except Exception as exc:
        post_survey_error = str(exc)

    # ── Calendar cross-reference analysis ────────────────────────────────────
    # Compares calendar registration slots against actual exam sessions (±20 min window).
    calendar_ghost_slots:      list[dict] = []   # registered slot, no matching session
    calendar_wrong_time_slots: list[dict] = []   # registered for one slot, exam at a different time
    calendar_mismatches:       list[dict] = []   # registered slot, but different student took exam
    sessions_no_slot:          list[dict] = []   # session with no matching calendar slot

    # ── Per-student summary ───────────────────────────────────────────────────
    # Build roster email → github_username map for calendar matching
    roster_email_to_user:    dict[str, str] = {}
    roster_username_to_email: dict[str, str] = {}
    try:
        from roster_utils import load_classroom_roster
        roster = load_classroom_roster()
        for ukey, entry in roster.items():
            if entry.email:
                roster_email_to_user[entry.email.lower()] = ukey
                roster_username_to_email[ukey] = entry.email
    except Exception:
        pass

    if calendar_events and records:
        try:
            import google_apis as _gapi
            # Parse calendar slots → (email, UTC datetime)
            cal_slots: list[tuple[str, datetime]] = []
            for email, dt_str in _gapi.extract_calendar_slots(calendar_events):
                dt = _parse_utc_dt(dt_str)
                if dt:
                    cal_slots.append((email, dt))

            # Build full_id → email map (same source used for grade email sending)
            xref_email_map = _load_student_email_map()

            # Parse session start times → (github_username, hebrew_name, full_id, UTC datetime)
            sess_list: list[tuple[str, Optional[str], str, datetime]] = []
            for r in records:
                dt = _parse_utc_dt(r.get("start_time") or "")
                if dt:
                    full_id = r.get("full_id") or r.get("full_id_from_repo") or ""
                    sess_list.append((r.get("github_username", ""), r.get("hebrew_name"), full_id, dt))

            _GHOST_SLOT_EXCLUDED_EMAILS = {"david.sarne"}

            # Build lowercase username → (hname, exam_dt) lookup for wrong-time detection.
            # Keyed lowercase because the roster returns lowercased usernames but session
            # records preserve the original GitHub casing (e.g. "DANSON27" vs "danson27").
            sess_by_uname: dict[str, tuple[Optional[str], datetime]] = {
                uname.lower(): (hname, sess_dt)
                for uname, hname, full_id, sess_dt in sess_list
            }

            # Build lowercase username → list of their own registered slot times.
            # Used to distinguish false-positive mismatches (student was at their own
            # adjacent slot) from true swaps (neither student has a matching own slot).
            own_slots_by_uname: dict[str, list[datetime]] = {}
            for _email, _slot_dt in cal_slots:
                _exp = roster_email_to_user.get(_email.lower())
                if _exp:
                    own_slots_by_uname.setdefault(_exp, []).append(_slot_dt)

            for email, slot_dt in cal_slots:
                if email.lower().split("@")[0] in _GHOST_SLOT_EXCLUDED_EMAILS:
                    continue

                matched = [
                    (uname, hname, full_id, sess_dt)
                    for uname, hname, full_id, sess_dt in sess_list
                    if abs((sess_dt - slot_dt).total_seconds()) <= 1200
                ]
                expected_uname = roster_email_to_user.get(email.lower())

                if not matched:
                    # No session within ±20 min — check if student took exam at a different time
                    if expected_uname and expected_uname in sess_by_uname:
                        hname, exam_dt = sess_by_uname[expected_uname]
                        calendar_wrong_time_slots.append({
                            "email":            email,
                            "slot_time":        slot_dt.isoformat(),
                            "exam_time":        exam_dt.isoformat(),
                            "github_username":  expected_uname,
                            "hebrew_name":      hname,
                        })
                    else:
                        # True ghost — flag if they have an invalidated session
                        has_invalidated = bool(expected_uname and expected_uname in invalidated_usernames)
                        calendar_ghost_slots.append({
                            "email":       email,
                            "slot_time":   slot_dt.isoformat(),
                            "invalidated": has_invalidated,
                        })
                else:
                    if expected_uname:
                        for uname, hname, full_id, sess_dt in matched:
                            if uname.lower() == expected_uname:
                                continue  # correct person at their own slot
                            actual_email = (
                                xref_email_map.get(full_id)
                                or roster_username_to_email.get(uname)
                            )
                            # Same email = same person, just a username mismatch in roster
                            if actual_email and actual_email.lower() == email.lower():
                                continue
                            # Only flag as swap if the "wrong" user has NO own slot matching
                            # their exam time — otherwise they were just at their own adjacent slot.
                            own_slots = own_slots_by_uname.get(uname.lower(), [])
                            if any(abs((sess_dt - s).total_seconds()) <= 1200 for s in own_slots):
                                continue  # student was at their own slot
                            calendar_mismatches.append({
                                "expected_email":      email,
                                "expected_username":   expected_uname,
                                "actual_username":     uname,
                                "actual_hebrew_name":  hname,
                                "actual_email":        actual_email,
                                "slot_time":           slot_dt.isoformat(),
                                "session_start_time":  sess_dt.isoformat(),
                            })

            _NO_SLOT_EXCLUDED_USERS = {"GreenPepper139"}
            _wrong_time_unames = {s["github_username"].lower() for s in calendar_wrong_time_slots}
            for uname, hname, full_id, sess_dt in sess_list:
                if uname in _NO_SLOT_EXCLUDED_USERS:
                    continue
                if uname.lower() in _wrong_time_unames:
                    continue  # already shown in purple (wrong-time) — don't double-list in blue
                if not any(abs((sess_dt - slot_dt).total_seconds()) <= 1200 for _, slot_dt in cal_slots):
                    sessions_no_slot.append({
                        "github_username": uname,
                        "hebrew_name":     hname,
                        "exam_start_time": sess_dt.isoformat(),
                    })
        except Exception as exc:
            print(f"[Admin] Calendar cross-reference error: {exc}")

    # ── Session timing stats ──────────────────────────────────────────────────
    session_durations_sec: list[float] = []
    ai_response_times_sec: list[float] = []

    for r in records:
        start_t  = _parse_utc_dt(r.get("start_time") or "")
        transcript_data = r.get("transcript")
        if not start_t or not isinstance(transcript_data, list) or not transcript_data:
            continue

        # Session duration: start_time → last transcript timestamp
        last_ts: Optional[datetime] = None
        for entry in reversed(transcript_data):
            ts_str = entry.get("question_shown_at") or entry.get("answer_submitted_at")
            if ts_str:
                last_ts = _parse_utc_dt(ts_str)
                break
        if last_ts:
            duration = (last_ts - start_t).total_seconds()
            if 60 <= duration <= 7200:
                session_durations_sec.append(duration)

        # AI response time: each student answer_submitted_at → next examiner question_shown_at
        for i, entry in enumerate(transcript_data):
            if entry.get("role") != "Student":
                continue
            ans_ts = _parse_utc_dt(entry.get("answer_submitted_at") or "")
            if not ans_ts:
                continue
            for next_entry in transcript_data[i + 1:]:
                if next_entry.get("role") == "Examiner":
                    q_ts = _parse_utc_dt(next_entry.get("question_shown_at") or "")
                    if q_ts:
                        diff = (q_ts - ans_ts).total_seconds()
                        if 1 <= diff <= 300:
                            ai_response_times_sec.append(diff)
                    break

    avg_session_minutes: Optional[float] = (
        round(sum(session_durations_sec) / len(session_durations_sec) / 60, 1)
        if session_durations_sec else None
    )
    avg_ai_response_seconds: Optional[float] = (
        round(sum(ai_response_times_sec) / len(ai_response_times_sec), 1)
        if ai_response_times_sec else None
    )

    student_rows = []
    for r in records:
        uname   = r.get("github_username", "")
        full_id = r.get("full_id") or r.get("full_id_from_repo") or ""
        sid     = r.get("student_id") or (full_id[-5:] if len(full_id) >= 5 else "")
        validation = validate_email_readiness(r)

        # Did this student register on the calendar? Match by roster email.
        on_calendar = None
        if calendar_emails is not None:
            try:
                from roster_utils import lookup_by_github_username
                entry = lookup_by_github_username(uname)
                on_calendar = bool(entry and entry.email.lower() in
                                   {e.lower() for e in calendar_emails})
            except Exception:
                on_calendar = None

        # Did this student fill the pre-survey? Match by student ID digits.
        filled_survey = None
        if survey_ids is not None and sid:
            filled_survey = any(sid in s_id or s_id in full_id for s_id in survey_ids)

        # Did this student fill the post-survey?
        filled_post_survey = None
        if post_survey_ids is not None and sid:
            filled_post_survey = any(sid in s_id or s_id in full_id for s_id in post_survey_ids)

        # Per-student session duration
        session_minutes: Optional[float] = None
        start_t = _parse_utc_dt(r.get("start_time") or "")
        tdata = r.get("transcript")
        if start_t and isinstance(tdata, list) and tdata:
            for entry in reversed(tdata):
                ts_str = entry.get("question_shown_at") or entry.get("answer_submitted_at")
                if ts_str:
                    last_ts = _parse_utc_dt(ts_str)
                    if last_ts:
                        dur = (last_ts - start_t).total_seconds()
                        if 60 <= dur <= 7200:
                            session_minutes = round(dur / 60, 1)
                    break

        student_rows.append({
            "github_username":    uname,
            "hebrew_name":        r.get("hebrew_name"),
            "full_id":            full_id or None,
            "graded":             True,
            "grade_email_sent":   r.get("grade_email_sent"),
            "email_valid":        validation["is_valid"],
            "missing_fields":     validation["missing_fields"],
            "on_calendar":        on_calendar,
            "filled_pre_survey":  filled_survey,
            "filled_post_survey": filled_post_survey,
            "session_minutes":    session_minutes,
        })

    result = {
        "assignment":            assignment,
        "graded_count":          len(records),
        "email_sent_count":      len(email_sent_usernames),
        "required_ids":          required_ids,
        "required_ids_error":    required_error,
        "calendar_count":        len(calendar_emails) if calendar_emails is not None else None,
        "calendar_by_day":       calendar_by_day,
        "calendar_by_hour":      calendar_by_hour,
        "calendar_error":        calendar_error,
        "calendar_cross_ref":    {
            "ghost_slots":      calendar_ghost_slots,
            "wrong_time_slots": calendar_wrong_time_slots,
            "mismatches":       calendar_mismatches,
            "no_slot":          sessions_no_slot,
        } if calendar_events is not None else None,
        "pre_survey_count":      len(survey_ids) if survey_ids is not None else None,
        "pre_survey_row_count":  survey_row_count,
        "pre_survey_error":      survey_error,
        "post_survey_count":      len(post_survey_ids) if post_survey_ids is not None else None,
        "post_survey_error":      post_survey_error,
        "avg_session_minutes":    avg_session_minutes,
        "avg_ai_response_seconds": avg_ai_response_seconds,
        "students":               student_rows,
    }
    _cache_set(assignment, "stats", result)
    return result


# ---------------------------------------------------------------------------
# GET /api/admin/assignment/{assignment}/question-stats
# ---------------------------------------------------------------------------

def _compute_question_stats(sessions: list, pool: list[dict]) -> list[dict]:
    """Parse transcripts and aggregate per-question statistics."""
    stats: dict[str, dict] = {}
    for q in pool:
        qid = q.get("id")
        if not qid:
            continue
        stats[qid] = {
            "id":            qid,
            "focus":         q.get("focus", ""),
            "files":         q.get("files", []),
            "difficulty":    q.get("difficulty", ""),
            "dimension":     q.get("dimension", ""),
            "times_asked":   0,
            "times_switched": 0,
            "times_reasked": 0,
            "_scores":       [],
        }

    for session in sessions:
        try:
            transcript: list[dict] = json.loads(session.transcript or "[]")
        except Exception:
            continue

        # Collect all real examiner entries (has chosen_topic.id, not a bare reask)
        real_examiner: list[tuple[int, dict]] = [
            (i, e)
            for i, e in enumerate(transcript)
            if e.get("role") == "Examiner"
            and isinstance(e.get("chosen_topic"), dict)
            and e["chosen_topic"].get("id")
        ]

        for j, (idx, e_entry) in enumerate(real_examiner):
            qid = e_entry["chosen_topic"]["id"]
            if qid not in stats:
                continue

            stats[qid]["times_asked"] += 1

            # Scan the entries immediately after this examiner entry (before the next
            # real question) to detect switch and re-ask on THIS question.
            switch_seen = reask_seen = False
            for after in transcript[idx + 1:]:
                role = after.get("role")
                if role == "Student":
                    if after.get("switch_event"):
                        switch_seen = True
                    if after.get("reask_triggered"):
                        reask_seen = True
                elif role == "Examiner":
                    if after.get("reask"):
                        continue  # bare re-ask entry — keep scanning
                    # First real next examiner entry: score here evaluates this question
                    raw = after.get("content")
                    content = raw if isinstance(raw, dict) else {}
                    ie = content.get("internalEvaluation")
                    score = ie.get("understandingScore") if isinstance(ie, dict) else None
                    if score is not None:
                        stats[qid]["_scores"].append(float(score))
                    break

            if switch_seen:
                stats[qid]["times_switched"] += 1
            if reask_seen:
                stats[qid]["times_reasked"] += 1

    result = []
    for s in stats.values():
        scores = s.pop("_scores")
        s["times_scored"] = len(scores)
        s["avg_score"]    = round(sum(scores) / len(scores), 2) if scores else None
        result.append(s)

    result.sort(key=lambda x: x["id"])
    return result


@app.get("/api/admin/assignment/{assignment}/question-stats")
def admin_question_stats(
    assignment: str,
    force: bool = False,
    background_tasks: BackgroundTasks = None,
    _: None = Depends(_require_admin),
    db: DBSession = Depends(get_db),
) -> dict:
    """
    Per-question statistics aggregated across all completed/graded sessions
    for the given assignment.  Parses the transcript JSON column in-process.
    """
    assignment = _require_known_assignment(assignment)
    if not force:
        cached, _ = _cache_get(assignment, "question_stats")
        if cached is not None:
            if background_tasks is not None:
                background_tasks.add_task(_bg_refresh_stats, assignment)
            return cached

    # Only count sessions from the new question pool onward.
    # Cutoff: 2026-05-18 15:00 Israel (EEST = UTC+3) = 2026-05-18 12:00 UTC (naive).
    _POOL_CUTOFF_UTC = datetime(2026, 5, 18, 12, 0, 0)

    sessions = (
        db.query(ExamSession)
        .filter(
            ExamSession.assignment_name == assignment,
            ExamSession.status.in_(["completed", "graded"]),
            ExamSession.start_time >= _POOL_CUTOFF_UTC,
        )
        .all()
    )

    try:
        pool, _ = _get_assignment_resources(assignment)
    except HTTPException:
        return {"error": f"Assignment '{assignment}' not found on this server.", "questions": []}

    questions = _compute_question_stats(sessions, pool)
    result = {
        "assignment":    assignment,
        "session_count": len(sessions),
        "questions":     questions,
    }
    _cache_set(assignment, "question_stats", result)
    return result


# ---------------------------------------------------------------------------
# GET /api/admin/student-sessions/{github_username}
# ---------------------------------------------------------------------------

@app.get("/api/admin/student-sessions/{github_username}")
def admin_student_sessions(
    github_username: str,
    _: None = Depends(_require_admin),
    db: DBSession = Depends(get_db),
) -> list[dict]:
    """Return all DB sessions for a student (used by invalidate UI)."""
    sessions = (
        db.query(ExamSession)
        .filter(func.lower(ExamSession.github_username) == github_username.strip().lower())
        .order_by(ExamSession.start_time.desc())
        .all()
    )
    seen_assignments: set[str] = set()
    result = []
    for s in sessions:
        key = s.assignment_name or ""
        if key in seen_assignments:
            continue
        seen_assignments.add(key)
        result.append({
            "assignment_name": s.assignment_name,
            "status":          s.status,
            "session_id":      s.session_id,
            "created_at":      s.start_time.isoformat() if s.start_time else None,
        })
    return result


# ---------------------------------------------------------------------------
# GET /api/admin/assignment/{assignment}/reminder-preview
# POST /api/admin/assignment/{assignment}/send-reminder-emails
# ---------------------------------------------------------------------------

def _load_student_email_map() -> dict[str, str]:
    """Load private/student_emails.csv from GCS → {full_id: email}."""
    mapping: dict[str, str] = {}
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        return mapping
    try:
        from github_stub import _gcs_client
        text = _gcs_client.bucket(bucket_name).blob("private/student_emails.csv").download_as_text(encoding="utf-8-sig")
        for row in csv.DictReader(io.StringIO(text)):
            full_id = (row.get("full_id") or "").strip()
            email   = (row.get("email")   or "").strip()
            if full_id and email:
                mapping[full_id] = email
    except Exception as exc:
        print(f"[Email map] Could not load student_emails.csv: {exc}")
    return mapping


@app.get("/api/admin/assignment/{assignment}/reminder-preview")
def admin_reminder_preview(
    assignment: str,
    _: None = Depends(_require_admin),
) -> dict:
    """
    Return the list of students who are in required_students_{assignment}.json
    but have NOT registered a calendar slot yet.
    """
    assignment = _require_known_assignment(assignment)
    # Required IDs
    try:
        bucket      = _get_admin_bucket()
        required_ids: list[str] = json.loads(
            bucket.blob(f"private/required_students_{assignment}.json").download_as_text()
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Required students list not found: {exc}")

    # Calendar registrations (emails)
    calendar_emails: set[str] = set()
    calendar_error:  Optional[str] = None
    try:
        import google_apis
        events         = google_apis.get_calendar_events()
        calendar_emails = {e.lower() for e in google_apis.extract_registered_emails(events)}
    except Exception as exc:
        calendar_error = str(exc)

    # Email map: full_id → email
    email_map = _load_student_email_map()

    # Build unregistered list
    students      = []
    no_email_ids  = []
    for full_id in required_ids:
        email = email_map.get(full_id, "")
        if not email:
            no_email_ids.append(full_id)
            continue
        if email.lower() in calendar_emails:
            continue
        name = _by_full_id.get(full_id, "")
        students.append({"full_id": full_id, "email": email, "name": name})

    default_subject = f"תזכורת: הרשמה לסשן הערכת ידע"
    default_body = (
        "שלום {name},\n\n"
        "שים לב: עדיין לא נרשמת לסשן הערכת הידע האוטומטי.\n"
        "הרשמה היא חובה לצורך קבלת הציון.\n\n"
        "לחץ על הקישור הבא כדי לבחור זמן נוח:\n"
        "{calendar_link}\n\n"
        "נא להירשם בהקדם.\n\n"
        "בברכה,\n"
        "צוות הקורס — מערכות הפעלה, אוניברסיטת בר-אילן\n\n"
        "---\n"
        "זהו מייל אוטומטי אין להשיב למייל זה."
    )

    return {
        "students":          students,
        "registered_count":  len(calendar_emails),
        "total_required":    len(required_ids),
        "no_email_count":    len(no_email_ids),
        "default_subject":   default_subject,
        "default_body":      default_body,
        "calendar_error":    calendar_error,
    }


@app.post("/api/admin/assignment/{assignment}/send-reminder-emails")
def admin_send_reminder_emails(
    assignment: str,
    body: dict,
    _: None = Depends(_require_admin),
) -> dict:
    """Send registration reminder emails to a selected subset of unregistered students."""
    assignment = _require_known_assignment(assignment)
    students:       list[dict] = body.get("students", [])
    subject:        str        = body.get("subject", "תזכורת: הרשמה לסשן הערכת ידע")
    body_template:  str        = body.get("body_template", "")
    calendar_link:  str        = body.get("calendar_link", "")

    smtp_user     = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.environ.get("SMTP_PORT", "587"))
    from_header = _COURSE_FROM_HEADER

    if not smtp_user or not smtp_password:
        raise HTTPException(status_code=503, detail="SMTP credentials (SMTP_USER / SMTP_PASSWORD) not configured.")

    sent   = 0
    failed = 0
    errors: list[str] = []

    context = ssl.create_default_context()
    try:
        srv = smtplib.SMTP(smtp_host, smtp_port)
        srv.ehlo()
        srv.starttls(context=context)
        srv.login(smtp_user, smtp_password)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"SMTP connection failed: {exc}")

    try:
        for s in students:
            email = (s.get("email") or "").strip()
            name  = s.get("name") or "סטודנט"
            if not email:
                failed += 1
                errors.append(f"no email for full_id={s.get('full_id', '?')}")
                continue

            filled_body = (
                body_template
                .replace("{name}", name)
                .replace("{calendar_link}", calendar_link or "[קישור לא הוגדר]")
            )

            msg            = MIMEText(filled_body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"]    = from_header
            msg["To"]      = email

            try:
                srv.sendmail(smtp_user, email, msg.as_string())
                sent += 1
                print(f"[Reminder] Sent to {email} ({name})")
            except Exception as exc:
                failed += 1
                errors.append(f"{email}: {exc}")
                print(f"[Reminder] Failed for {email}: {exc}")
    finally:
        try:
            srv.quit()
        except Exception:
            pass

    return {"sent": sent, "failed": failed, "errors": errors}


# ---------------------------------------------------------------------------
# POST /api/admin/send-test-grade-email
# ---------------------------------------------------------------------------

@app.post("/api/admin/send-test-grade-email")
def admin_send_test_grade_email(
    to: str = Query("shacharsl97@gmail.com", description="Recipient email address"),
    _: None = Depends(_require_admin),
) -> dict:
    """
    Send a synthetic grade email to `to` so you can preview the template before
    the real release.  Uses fake but realistic data — does not touch the DB or GCS,
    and never marks anything as sent.
    """
    from grade_email_template import build_grade_email

    fake_blob = {
        "github_username": "test-student",
        "hebrew_name": "ישראל ישראלי",
        "student_id": "123456789",
        "final_grade": {
            "oralDefenseScore":       82,
            "staticCodeQualityScore": 75,
            "finalWeightedGrade":     80,
        },
        "grader_verdict": {
            "studentFeedback": (
                "הסטודנט הפגין הבנה טובה של מנגנוני הסנכרון. "
                "הסבר ה-mutex היה מדויק ומפורט, והסטודנט ידע להצביע על בעיות אפשריות בקוד שלו. "
                "עם זאת, היה קושי מסוים בהסבר מלא של תנאי מרוץ בתרחיש ספציפי שהועלה בשאלה השנייה."
            ),
        },
        "code_review": {
            "studentStaticFeedback": (
                "הקוד מאורגן היטב ומשתמש בהפרדת אחריות ברורה בין הקבצים. "
                "ניהול שגיאות מקיף ונכון לרוב נתיבי הביצוע. "
                "נקודות לשיפור: הוספת הערות לחלקים מורכבים ושיפור שמות משתנים בפונקציות הפנימיות."
            ),
        },
    }

    subject, body = build_grade_email(fake_blob)

    smtp_user     = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.environ.get("SMTP_PORT", "587"))

    if not smtp_user or not smtp_password:
        raise HTTPException(status_code=503, detail="SMTP_USER / SMTP_PASSWORD not configured.")

    from grade_email_template import build_grade_email_html
    html_body = build_grade_email_html(body)

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[TEST] {subject}"
        msg["From"]    = _COURSE_FROM_HEADER
        msg["To"]      = to
        msg.attach(MIMEText(body,      "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html",  "utf-8"))
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as srv:
            srv.ehlo()
            srv.starttls(context=context)
            srv.login(smtp_user, smtp_password)
            srv.sendmail(smtp_user, to, msg.as_string())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SMTP error: {exc}")

    print(f"[TestEmail] Sent test grade email to {to}")
    return {"sent": True, "to": to, "subject": f"[TEST] {subject}", "body": body}


# ---------------------------------------------------------------------------
# POST /api/admin/send-test-reminder-email
# ---------------------------------------------------------------------------

@app.post("/api/admin/send-test-reminder-email")
def admin_send_test_reminder_email(
    to: str = Query("shacharsl97@gmail.com", description="Recipient email address"),
    _: None = Depends(_require_admin),
) -> dict:
    """
    Send a sample registration-reminder email so the From address / display name
    can be verified before a real batch send.  Uses placeholder text and a dummy
    calendar link — does not touch the DB, GCS, or the student list.
    """
    smtp_user     = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.environ.get("SMTP_PORT", "587"))
    from_header = _COURSE_FROM_HEADER

    if not smtp_user or not smtp_password:
        raise HTTPException(status_code=503, detail="SMTP_USER / SMTP_PASSWORD not configured.")

    subject = "[TEST] תזכורת: הרשמה לסשן הערכת ידע"
    body    = (
        "שלום ישראל ישראלי,\n\n"
        "זוהי הודעת בדיקה — לא נדרשת כל פעולה מצדך.\n\n"
        "בפועל, ההודעה תכיל תזכורת להירשם לסשן הערכת ידע בקישור:\n"
        "https://calendar.google.com/example\n\n"
        "בברכה,\nצוות מערכות הפעלה\n\n"
        "---\n"
        "זהו מייל אוטומטי אין להשיב למייל זה."
    )

    try:
        msg            = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"]    = from_header
        msg["To"]      = to
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as srv:
            srv.ehlo()
            srv.starttls(context=context)
            srv.login(smtp_user, smtp_password)
            srv.sendmail(smtp_user, to, msg.as_string())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SMTP error: {exc}")

    print(f"[TestEmail] Sent test reminder email to {to} (from_header={from_header!r})")
    return {"sent": True, "to": to, "from": from_header, "subject": subject}


# ---------------------------------------------------------------------------
# Assignment bonus (e.g. optional REPORT.md, up to +5)
# ---------------------------------------------------------------------------
# Sourced from a GCS CSV (github_username,bonus) so it can be updated without a
# code change or a regrade. Applied to the final grade at email-send time — like
# the adaptation bonus — and never stored on the result blob. Only assignment-2
# carries a bonus today; other assignments resolve to 0.
_ASS2_BONUS_GCS_PATH = os.environ.get("ASS2_BONUS_GCS_PATH", "private/assignment-2_bonus.csv")
_BONUS_ASSIGNMENTS = {"assignment-2"}


def _load_bonus_map() -> dict[str, int]:
    """Load {github_username_lower: bonus_points} from the GCS bonus CSV (>0 only)."""
    out: dict[str, int] = {}
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        return out
    try:
        from github_stub import _gcs_client
        text = _gcs_client.bucket(bucket_name).blob(_ASS2_BONUS_GCS_PATH).download_as_text(encoding="utf-8-sig")
        for row in csv.DictReader(io.StringIO(text)):
            u = (row.get("github_username") or "").strip().lower()
            try:
                b = int(float((row.get("bonus") or "0").strip()))
            except ValueError:
                b = 0
            if u and b > 0:
                out[u] = b
        print(f"[BonusMap] Loaded {len(out)} bonus entries from {_ASS2_BONUS_GCS_PATH}.")
    except Exception as exc:
        print(f"[BonusMap] Could not load {_ASS2_BONUS_GCS_PATH}: {exc}")
    return out


def _bonus_for(assignment_name: str, github_username: str, bonus_map: dict[str, int]) -> int:
    """Per-student assignment bonus, matched case-insensitively by github_username."""
    if assignment_name not in _BONUS_ASSIGNMENTS:
        return 0
    return bonus_map.get((github_username or "").strip().lower(), 0)


def _send_grade_email_smtp(
    blob_data: dict, student_email: str, extra_bonus: int,
    smtp_user: str, smtp_password: str, smtp_host: str, smtp_port: int,
    connection_bonus: int = 0,
) -> None:
    """Build (with bonus) and send a single grade email. Raises on SMTP failure."""
    from grade_email_template import build_grade_email, build_grade_email_html
    subject, body = build_grade_email(blob_data, extra_bonus=extra_bonus,
                                      connection_bonus=connection_bonus)
    html_body = build_grade_email_html(body)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = _COURSE_FROM_HEADER
    msg["To"]      = student_email
    msg.attach(MIMEText(body,      "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html",  "utf-8"))
    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as srv:
        srv.ehlo()
        srv.starttls(context=context)
        srv.login(smtp_user, smtp_password)
        srv.sendmail(smtp_user, student_email, msg.as_string())


# ---------------------------------------------------------------------------
# POST /api/cron/send-grade-emails
# ---------------------------------------------------------------------------

@app.post("/api/cron/send-grade-emails")
def cron_send_grade_emails(
    _: None = Depends(_require_admin),
) -> dict:
    """
    Send grade emails to every graded-but-not-yet-emailed student across all assignments.
    Called daily by Cloud Scheduler (10 AM Israel time) and manually for first release.
    Auth: X-Admin-Key header (same as other admin endpoints).
    """
    from grade_email_template import validate_email_readiness
    from github_stub import _gcs_client
    from models import Session as ExamSession
    from database import SessionLocal

    smtp_user     = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.environ.get("SMTP_PORT", "587"))

    if not smtp_user or not smtp_password:
        raise HTTPException(status_code=503, detail="SMTP_USER / SMTP_PASSWORD not configured.")

    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        raise HTTPException(status_code=503, detail="GCS_SUBMISSIONS_BUCKET not configured.")

    bucket    = _gcs_client.bucket(bucket_name)
    email_map = _load_student_email_map()
    bonus_map = _load_bonus_map()

    db  = SessionLocal()
    sent = skipped = errors = 0
    log: list[dict] = []

    # Cutoff: today's midnight in Israel time (UTC+3, EEST May–Oct).
    # Sessions that *started* at or after midnight today (Israel) wait for tomorrow's job,
    # so a 9 AM session today is excluded and lands in the next run.
    _ISRAEL_UTC_OFFSET = timedelta(hours=3)
    _now_il = datetime.utcnow() + _ISRAEL_UTC_OFFSET
    _today_midnight_utc = datetime(
        _now_il.year, _now_il.month, _now_il.day,
        tzinfo=None,
    ) - _ISRAEL_UTC_OFFSET  # naive UTC for DB comparison

    try:
        sessions = (
            db.query(ExamSession)
              .filter(ExamSession.status == "graded")
              .filter(ExamSession.grade_email_sent.isnot(True))
              .filter(ExamSession.start_time < _today_midnight_utc)
              .all()
        )
        print(f"[GradeEmail] {len(sessions)} unsent graded session(s) found "
              f"(cutoff: {_today_midnight_utc.isoformat()} UTC = midnight Israel).")

        for s in sessions:
            blob_path = f"results/{s.assignment_name}/{s.github_username}.json"
            try:
                blob_data = json.loads(bucket.blob(blob_path).download_as_text())
            except Exception as exc:
                print(f"[GradeEmail] ERROR loading blob {blob_path}: {exc}")
                errors += 1
                log.append({"username": s.github_username, "status": "error_blob"})
                continue

            # full_id_from_repo may be None in DB — fall back to the blob which has it
            full_id = (
                s.full_id_from_repo
                or blob_data.get("full_id")
                or blob_data.get("full_id_from_repo")
                or ""
            )
            student_email = (email_map.get(full_id) or "").strip()

            if not student_email:
                print(f"[GradeEmail] SKIP {s.github_username} — no email for id={full_id!r}")
                skipped += 1
                log.append({"username": s.github_username, "status": "skipped_no_email", "full_id": full_id})
                continue

            validation = validate_email_readiness(blob_data)
            if not validation["is_valid"]:
                print(f"[GradeEmail] SKIP {s.github_username} — not ready: {validation['missing_fields']}")
                skipped += 1
                log.append({"username": s.github_username, "status": "skipped_not_ready",
                             "missing": validation["missing_fields"]})
                continue

            extra_bonus = _bonus_for(s.assignment_name, s.github_username, bonus_map)
            try:
                _send_grade_email_smtp(blob_data, student_email, extra_bonus,
                                       smtp_user, smtp_password, smtp_host, smtp_port)
            except Exception as exc:
                print(f"[GradeEmail] ERROR sending to {student_email}: {exc}")
                errors += 1
                log.append({"username": s.github_username, "status": "error_send"})
                continue

            s.grade_email_sent = True
            db.commit()

            try:
                blob_data["grade_email_sent"] = True
                bucket.blob(blob_path).upload_from_string(
                    json.dumps(blob_data, ensure_ascii=False, indent=2),
                    content_type="application/json; charset=utf-8",
                )
            except Exception as exc:
                print(f"[GradeEmail] WARNING: DB updated but blob not updated for {s.github_username}: {exc}")

            print(f"[GradeEmail] Sent to {student_email} ({s.github_username}) bonus={extra_bonus}")
            sent += 1
            log.append({"username": s.github_username, "status": "sent", "email": student_email, "bonus": extra_bonus})

    finally:
        db.close()

    print(f"[GradeEmail] Done. sent={sent} skipped={skipped} errors={errors}")
    return {"sent": sent, "skipped": skipped, "errors": errors, "log": log}


# ---------------------------------------------------------------------------
# POST /api/admin/resend-grade-emails
# ---------------------------------------------------------------------------

@app.post("/api/admin/resend-grade-emails")
def admin_resend_grade_emails(
    body: ResendGradeEmailsRequest,
    _: None = Depends(_require_admin),
) -> dict:
    """
    Force-resend grade emails for an explicit list of github usernames, *ignoring*
    the already-sent flag, applying the per-student assignment bonus.

    Intended for one-off corrections (e.g. students who were emailed before the
    REPORT.md bonus existed). Each call re-sends to every listed user — call it
    deliberately, not on a schedule, to avoid duplicate emails.
    Auth: X-Admin-Key header.
    """
    from grade_email_template import validate_email_readiness
    from github_stub import _gcs_client
    from models import Session as ExamSession
    from database import SessionLocal

    smtp_user     = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.environ.get("SMTP_PORT", "587"))
    if not smtp_user or not smtp_password:
        raise HTTPException(status_code=503, detail="SMTP_USER / SMTP_PASSWORD not configured.")

    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        raise HTTPException(status_code=503, detail="GCS_SUBMISSIONS_BUCKET not configured.")

    assignment = body.assignment
    bucket     = _gcs_client.bucket(bucket_name)
    email_map  = _load_student_email_map()
    bonus_map  = _load_bonus_map()

    db = SessionLocal()
    sent = skipped = errors = 0
    results: list[dict] = []
    try:
        for uname in body.usernames:
            s = (
                db.query(ExamSession)
                  .filter(ExamSession.github_username == uname)
                  .filter(ExamSession.assignment_name == assignment)
                  .filter(ExamSession.status == "graded")
                  .order_by(ExamSession.start_time.desc())
                  .first()
            )
            if not s:
                skipped += 1
                results.append({"username": uname, "status": "no_graded_session"})
                continue

            blob_path = f"results/{assignment}/{s.github_username}.json"
            try:
                blob_data = json.loads(bucket.blob(blob_path).download_as_text())
            except Exception as exc:
                errors += 1
                results.append({"username": uname, "status": "error_blob", "detail": str(exc)[:200]})
                continue

            full_id = (
                s.full_id_from_repo
                or blob_data.get("full_id")
                or blob_data.get("full_id_from_repo")
                or ""
            )
            student_email = (email_map.get(full_id) or "").strip()
            if not student_email:
                skipped += 1
                results.append({"username": uname, "status": "skipped_no_email", "full_id": full_id})
                continue

            validation = validate_email_readiness(blob_data)
            if not validation["is_valid"]:
                skipped += 1
                results.append({"username": uname, "status": "skipped_not_ready",
                                "missing": validation["missing_fields"]})
                continue

            extra_bonus = _bonus_for(assignment, s.github_username, bonus_map)
            try:
                _send_grade_email_smtp(blob_data, student_email, extra_bonus,
                                       smtp_user, smtp_password, smtp_host, smtp_port,
                                       connection_bonus=body.connection_bonus)
            except Exception as exc:
                errors += 1
                results.append({"username": uname, "status": "error_send", "detail": str(exc)[:200]})
                continue

            s.grade_email_sent = True
            db.commit()
            try:
                blob_data["grade_email_sent"] = True
                bucket.blob(blob_path).upload_from_string(
                    json.dumps(blob_data, ensure_ascii=False, indent=2),
                    content_type="application/json; charset=utf-8",
                )
            except Exception:
                pass

            print(f"[ResendGrade] Sent to {student_email} ({s.github_username}) "
                  f"bonus={extra_bonus} connection_bonus={body.connection_bonus}")
            sent += 1
            results.append({"username": uname, "status": "sent", "email": student_email,
                            "bonus": extra_bonus, "connection_bonus": body.connection_bonus})
    finally:
        db.close()

    print(f"[ResendGrade] Done. sent={sent} skipped={skipped} errors={errors}")
    return {"assignment": assignment, "sent": sent, "skipped": skipped, "errors": errors, "results": results}


# ---------------------------------------------------------------------------
# POST /api/cron/send-reminder-emails
# ---------------------------------------------------------------------------

@app.post("/api/cron/send-reminder-emails")
def cron_send_reminder_emails(
    days_ahead: int = 1,
    _: None = Depends(_require_admin),
) -> dict:
    """
    Send day-before exam reminder emails to students whose exam slot is `days_ahead`
    days from now (default: tomorrow).  Fetches slots from Google Calendar, resolves
    GitHub usernames from the classroom roster, and emails repo check links.
    Called daily by Cloud Scheduler (18:00 Israel time).
    Auth: X-Admin-Key header.
    """
    from google_apis import get_calendar_events, _ORGANISER_EMAIL
    from roster_utils import load_classroom_roster
    from zoneinfo import ZoneInfo
    from email.utils import formataddr as _formataddr

    smtp_user     = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.environ.get("SMTP_PORT", "587"))
    github_org    = os.environ.get("GITHUB_ORG", "").strip()

    if not smtp_user or not smtp_password:
        raise HTTPException(status_code=503, detail="SMTP_USER / SMTP_PASSWORD not configured.")

    _LOCAL_TZ   = ZoneInfo("Asia/Jerusalem")
    _now_local  = datetime.now(_LOCAL_TZ)
    target_date = (_now_local + timedelta(days=days_ahead)).date()

    # ── Fetch calendar slots for target date ────────────────────────────────
    day_start = datetime(target_date.year, target_date.month, target_date.day,
                         0, 0, 0, tzinfo=_LOCAL_TZ)
    day_end   = day_start + timedelta(days=1)

    events = get_calendar_events(
        time_min=day_start.isoformat(),
        time_max=day_end.isoformat(),
    )
    print(f"[ReminderEmail] target={target_date}  events={len(events)}")

    org_lower = _ORGANISER_EMAIL.lower()
    slots: list[tuple[str, str]] = []
    for ev in events:
        dt_str = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date", "")
        if "T" in dt_str:
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                exam_time = dt.astimezone(_LOCAL_TZ).strftime("%H:%M")
            except Exception:
                exam_time = dt_str[11:16]
        else:
            exam_time = ""
        for att in ev.get("attendees", []):
            email = att.get("email", "").strip().lower()
            if email and email != org_lower:
                slots.append((email, exam_time))

    if not slots:
        print(f"[ReminderEmail] No slots for {target_date} — nothing to send.")
        return {"sent": 0, "skipped": 0, "errors": 0, "target_date": str(target_date), "log": []}

    # ── Load roster (email → github_username) ───────────────────────────────
    roster    = load_classroom_roster()
    by_email  = {entry.email.strip().lower(): entry
                 for entry in roster.values() if entry.email.strip()}

    sent = skipped = errors = 0
    log: list[dict] = []

    for calendar_email, exam_time in slots:
        entry = by_email.get(calendar_email)
        if entry:
            github_username = entry.github_username
            first_name      = entry.first_name_he
        else:
            github_username = "<your-github-username>"
            first_name      = ""
            print(f"[ReminderEmail] {calendar_email} not in roster — using placeholder")

        base  = f"https://github.com/{github_org}" if github_org else "https://github.com/<ORG>"
        a1    = f"{base}/biu-os-2026-assignment-1-claude-code-shell-hooks-{github_username}"
        a2    = f"{base}/assignment-2-{github_username}"
        a3    = f"{base}/assignment-3-{github_username}"

        greeting  = f"שלום {first_name}," if first_name else "שלום,"
        time_note = f" בשעה {exam_time}" if exam_time else ""

        subject = "תזכורת: הערכת ידע אוטומטית מחר — ודאו שהקוד שלכם ב-GitHub"
        body    = f"""\
{greeting}

תזכורת: מחר{time_note} תתקיים הערכת הידע האוטומטית שלכם במסגרת קורס מערכות הפעלה.

לפני הבחינה, אנא ודאו שהקוד שלכם מופיע ב-GitHub בריפוזיטורי הנכון.
זאת אחת הסיבות השכיחות לתקלות — סטודנטים שמגלים רק בזמן הבחינה שהקוד לא הועלה.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
בדקו את הקוד שלכם בלינקים הבאים:

מטלה 1:
{a1}

מטלה 2:
{a2}

מטלה 3:
{a3}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

אם הריפוזיטורי לא נמצא — בדקו גם עם סיומת ‎-2 או ‎-3 בסוף השם
(לדוגמה: assignment-2-<username>-2).
GitHub Classroom יוצר לפעמים שמות כאלה בהרשמה חוזרת.

אם הקוד שלכם לא מופיע בכלל — דחפו אותו (git push) לריפוזיטורי הנכון לפני הבחינה.
ללא הקוד, המערכת לא תוכל להתחיל את הבחינה.

בהצלחה מחר!
צוות הקורס — מערכות הפעלה, אוניברסיטת בר-אילן

---
זהו מייל אוטומטי — אין להשיב למייל זה.
"""

        import html as _html
        html_body = f"""\
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"><style>
body{{font-family:Arial,sans-serif;direction:rtl;text-align:right;color:#222;
     max-width:600px;margin:0 auto;padding:20px;font-size:14px;line-height:1.7}}
pre{{font-family:Arial,sans-serif;white-space:pre-wrap;word-break:break-word;
    direction:rtl;text-align:right;margin:0}}
</style></head>
<body><pre>{_html.escape(body)}</pre></body></html>"""

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = _COURSE_FROM_HEADER
            msg["To"]      = _formataddr((first_name, calendar_email)) if first_name else calendar_email
            msg.attach(MIMEText(body,      "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html",  "utf-8"))
            ctx = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port) as srv:
                srv.ehlo()
                srv.starttls(context=ctx)
                srv.login(smtp_user, smtp_password)
                srv.sendmail(smtp_user, calendar_email, msg.as_string())
            print(f"[ReminderEmail] Sent to {calendar_email} (github={github_username})")
            sent += 1
            log.append({"email": calendar_email, "github": github_username, "status": "sent"})
        except Exception as exc:
            print(f"[ReminderEmail] ERROR sending to {calendar_email}: {exc}")
            errors += 1
            log.append({"email": calendar_email, "github": github_username, "status": "error", "detail": str(exc)})

    print(f"[ReminderEmail] Done. sent={sent} skipped={skipped} errors={errors}")
    return {"sent": sent, "skipped": skipped, "errors": errors, "target_date": str(target_date), "log": log}


# ---------------------------------------------------------------------------
# POST /api/admin/regrade/{session_id}
# ---------------------------------------------------------------------------

@app.post("/api/admin/regrade/{session_id}")
def admin_regrade(
    session_id: str,
    _: None = Depends(_require_admin),
) -> dict:
    """Re-run code reviewer + grader for an existing session (synchronous — waits for completion)."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        session = db.query(ExamSession).filter(ExamSession.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found.")
    finally:
        db.close()
    run_grader_background(session_id)
    return {"status": "regrade_complete", "session_id": session_id}


# ---------------------------------------------------------------------------
# GET /api/admin/results/aggregate_fast  (result_summary-backed; see MULTI_COURSE_MIGRATION §4.10)
# ---------------------------------------------------------------------------
# Same response shape as /aggregate, but reads the small `result_summary` table
# (~550 tiny rows) instead of downloading every GCS blob (35 MB for a-3, which OOM'd
# instances). Additive and safe: the blob path above is untouched and remains the
# fallback. Returns {"empty_table": true} if the table hasn't been backfilled yet, so a
# caller can fall back to /aggregate. Populate with scripts/backfill_result_summary.py and
# keep fresh via the RESULT_SUMMARY_ENABLED funnel in run_grader_background.

def _summary_row_to_student(row) -> dict:
    """Shape a ResultSummary row like _student_summary() so the frontend contract matches."""
    return {
        "github_username":       row.github_username,
        "student_id":            row.student_id,
        "hebrew_name":           row.hebrew_name,
        "final_grade":           row.final_grade,
        "oral_score":            row.oral_score,
        "code_score":            row.static_score,
        "authorship_assessment": row.authorship,
        "integrity_flag":        row.integrity_flag,
        "prompt_injection_flag": row.prompt_injection_flag,
        "id_resolution_status":  row.id_resolution_status,
        "timed_out":             row.timed_out,
        "switch_used":           row.switch_used,
        "exam_start_time":       row.exam_date.isoformat() if row.exam_date else None,
        "session_minutes":       row.duration_min,
    }


@app.get("/api/admin/results/aggregate_fast")
def admin_aggregate_fast(
    assignment: str = Query(..., description="Assignment name"),
    db: DBSession = Depends(get_db),
    _: None = Depends(_require_admin),
) -> dict:
    """SQL-backed aggregate — no blob download. Same shape as /aggregate."""
    from models import ResultSummary
    assignment = _require_known_assignment(assignment)

    rows = db.query(ResultSummary).filter(ResultSummary.assignment_name == assignment).all()
    if not rows:
        # Either no such assignment, or the table isn't backfilled. Signal so the caller
        # can fall back to the blob-backed /aggregate.
        return {"assignment": assignment, "count": 0, "empty_table": True}

    graded = [r for r in rows if r.status != "invalidated"]
    count = len(graded)
    if count == 0:
        return {"assignment": assignment, "count": 0}

    def _safe_stats(vals: list) -> Optional[dict]:
        vals = [v for v in vals if isinstance(v, (int, float))]
        if not vals:
            return None
        return {"mean": round(statistics.mean(vals), 1), "median": statistics.median(vals),
                "min": min(vals), "max": max(vals)}

    oral_scores  = [r.oral_score for r in graded]
    code_scores  = [r.static_score for r in graded]
    final_grades = [r.final_grade for r in graded]

    histogram = [0] * 10
    for g in final_grades:
        if isinstance(g, (int, float)):
            histogram[min(int(g) // 10, 9)] += 1

    flagged = [_summary_row_to_student(r) for r in graded
               if r.integrity_flag or r.prompt_injection_flag or r.authorship == "not_established"]
    outliers = sorted([_summary_row_to_student(r) for r in graded if r.final_grade is not None],
                      key=lambda s: (s["final_grade"] or 100))[:10]

    return {
        "assignment":      assignment,
        "count":           count,
        "source":          "result_summary",
        "stats": {
            "oral_defense": _safe_stats(oral_scores),
            "code_quality": _safe_stats(code_scores),
            "final_grade":  _safe_stats(final_grades),
        },
        "histogram": {
            "labels": [f"{i*10}–{i*10+9 if i < 9 else 100}" for i in range(10)],
            "values": histogram,
        },
        "authorship":      dict(Counter(r.authorship or "unknown" for r in graded)),
        "id_resolution":   dict(Counter(r.id_resolution_status or "unknown" for r in graded)),
        "timed_out_count": sum(1 for r in graded if r.timed_out),
        "flagged":         flagged,
        "outliers":        outliers,
        "all_students":    [_summary_row_to_student(r) for r in graded],
    }


# ---------------------------------------------------------------------------
# GET /api/admin/results/item-analysis  (read-only; served from a GCS report blob)
# ---------------------------------------------------------------------------
# Read-only question-pool item-analysis panel (MULTI_COURSE_MIGRATION §4.8). The report is
# computed OFFLINE by `scripts/item_analysis.py --write-gcs --assignment X` (which needs the
# sentence-transformers dep, kept OUT of the backend image) and stored as a GCS blob. This
# endpoint just returns that stored blob. "Recompute" = re-run the script; there is no
# compute in the request path, so no heavy dependency and no per-request cost.

@app.get("/api/admin/results/item-analysis")
def admin_item_analysis(
    assignment: str = Query(..., description="Assignment name"),
    _: None = Depends(_require_admin),
) -> dict:
    """Return the stored item-analysis report for an assignment, or {computed: false}."""
    from config import ITEM_ANALYSIS_GCS_PATH
    assignment = _require_known_assignment(assignment)
    bucket = _get_admin_bucket()
    blob = bucket.blob(ITEM_ANALYSIS_GCS_PATH.format(assignment=assignment))
    if not blob.exists():
        return {
            "assignment": assignment,
            "computed": False,
            "hint": ("No report yet. Run offline: "
                     f"python scripts/item_analysis.py --assignment {assignment} --write-gcs"),
        }
    report = json.loads(blob.download_as_text())
    report["computed"] = True
    return report


# ---------------------------------------------------------------------------
# GET /api/admin/results/export.csv
# ---------------------------------------------------------------------------

@app.get("/api/admin/results/export.csv")
def admin_export_csv(
    assignment: str = Query(..., description="Assignment name"),
    _: None = Depends(_require_admin),
) -> StreamingResponse:
    """Download all results as a UTF-8 BOM CSV."""
    assignment = _require_known_assignment(assignment)
    records, _ = _load_assignment_blobs(assignment)
    records.sort(key=lambda r: r.get("github_username") or "")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "github_username", "student_id", "full_id", "hebrew_name",
        "id_resolution_status",
        "oral_defense_score", "code_quality_score", "final_weighted_grade",
        "authorship_assessment", "integrity_flag", "prompt_injection_flag",
        "timed_out", "start_time",
    ])
    for r in records:
        fg = r.get("final_grade") or {}
        gv = r.get("grader_verdict") or {}
        writer.writerow([
            r.get("github_username", ""),
            r.get("student_id", ""),
            r.get("full_id", "") or r.get("full_id_from_repo", ""),
            r.get("hebrew_name", ""),
            r.get("id_resolution_status", ""),
            fg.get("oralDefenseScore", ""),
            fg.get("staticCodeQualityScore", ""),
            fg.get("finalWeightedGrade", ""),
            gv.get("authorshipAssessment", ""),
            gv.get("integrityFlag", ""),
            gv.get("promptInjectionFlag", ""),
            r.get("timed_out", ""),
            r.get("start_time", ""),
        ])

    csv_bytes = ("﻿" + output.getvalue()).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{assignment}_results.csv"'},
    )


# ---------------------------------------------------------------------------
# GET /api/admin/results/{github_username}  (wildcard — must stay AFTER specific paths above)
# ---------------------------------------------------------------------------

@app.get("/api/admin/results/{github_username}", response_model=ResultsResponse)
def get_results(
    github_username: str,
    db: DBSession = Depends(get_db),
) -> ResultsResponse:
    """
    Professor view: returns all sessions for a student with full log + grade.
    """
    sessions = (
        db.query(ExamSession)
        .filter(func.lower(ExamSession.github_username) == github_username.strip().lower())
        .order_by(ExamSession.start_time.desc())
        .all()
    )

    def _parse_json(raw: Optional[str]) -> Optional[object]:
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    summaries = [
        SessionSummary(
            session_id       = s.session_id,
            start_time       = s.start_time.isoformat() if s.start_time else "",
            status           = s.status,
            final_grade      = _parse_json(s.final_grade),
            professor_report = s.professor_report,
            transcript       = _parse_json(s.transcript),
            code_review      = _parse_json(s.code_review),
            grader_verdict   = _parse_json(s.grader_verdict),
        )
        for s in sessions
    ]

    return ResultsResponse(
        github_username = github_username,
        sessions        = summaries,
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/config")
def exam_config():
    """Per-deployment UI configuration, read by the entry screens before the student has
    typed anything.

    It has to come from the backend at runtime rather than a build arg: one frontend image
    serves every course, so nothing course-specific can be baked in. `identity_mode` is
    derived from FORM_SOURCES via config.identity_mode_for, so registering a Form assignment
    switches the wording too — there is no second switch to forget.
    """
    ui = course_ui()
    return {
        "identity_mode": identity_mode_for(DEFAULT_ASSIGNMENT),
        "course_title_he": ui["title_he"],
        # "code" | "solution" — OS students submit code, maths students submit a written
        # solution. Calling a proof "your code" reads as a bug to the student.
        "submission_kind": ui["submission_kind"],
        # Everything this deployment can examine, for the "that's not my assignment"
        # chooser. Course-scoped via KNOWN_ASSIGNMENTS, so one course's assignments can
        # never be offered by another's. A single-assignment course yields one entry and
        # the chooser hides itself.
        "assignments": [
            {
                "name": a,
                "label_he": ASSIGNMENT_LABELS.get(a, {}).get("he", a),
                "label_en": ASSIGNMENT_LABELS.get(a, {}).get("en", a),
            }
            for a in KNOWN_ASSIGNMENTS
        ],
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}
