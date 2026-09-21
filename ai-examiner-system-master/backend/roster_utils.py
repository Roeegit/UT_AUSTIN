"""
roster_utils.py — GitHub Classroom roster lookup (github_username → name + email).

Data source priority:
  1. GCS:   private/classroom_roster.csv  (production)
  2. Local: backend/roster/classroom_roster.csv  (dev)

The classroom_roster.csv columns are:
  identifier     — "first_name_HE,last_name_HE,email[,]"  (comma-separated within the field)
  github_username
  github_id
  name           — GitHub display name (often empty)
"""

import csv
import io
import os
from dataclasses import dataclass
from pathlib import Path

ROSTER_GCS_PATH   = "private/classroom_roster.csv"
_LOCAL_PATH       = Path(__file__).parent / "roster" / "classroom_roster.csv"


@dataclass
class RosterEntry:
    github_username: str
    first_name_he:   str
    last_name_he:    str
    email:           str

    @property
    def full_name_he(self) -> str:
        return f"{self.first_name_he} {self.last_name_he}".strip()


def _load_raw() -> str:
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if bucket_name:
        try:
            from github_stub import _gcs_client
            text = _gcs_client.bucket(bucket_name).blob(ROSTER_GCS_PATH).download_as_text(
                encoding="utf-8-sig"
            )
            print(f"[Roster] Loaded from GCS: {ROSTER_GCS_PATH}")
            return text
        except Exception as exc:
            print(f"[Roster] GCS load failed ({exc}), trying local file...")

    if _LOCAL_PATH.exists():
        print(f"[Roster] Loaded from local: {_LOCAL_PATH}")
        return _LOCAL_PATH.read_text(encoding="utf-8-sig")

    raise FileNotFoundError(
        f"Classroom roster not found in GCS ({ROSTER_GCS_PATH}) or locally ({_LOCAL_PATH}). "
        "Upload it via: gsutil cp backend/roster/classroom_roster.csv "
        "gs://$GCS_SUBMISSIONS_BUCKET/private/classroom_roster.csv"
    )


def load_classroom_roster() -> dict[str, RosterEntry]:
    """
    Return {github_username_lower: RosterEntry} for every student in the roster.
    Strips trailing commas and whitespace from identifier parts.
    """
    raw    = _load_raw()
    result: dict[str, RosterEntry] = {}

    for row in csv.DictReader(io.StringIO(raw)):
        username = row.get("github_username", "").strip()
        if not username:
            continue

        identifier = row.get("identifier", "").strip().strip('"')
        parts      = [p.strip().rstrip(",").strip() for p in identifier.split(",")]

        first = parts[0] if len(parts) > 0 else ""
        last  = parts[1] if len(parts) > 1 else ""
        email = parts[2] if len(parts) > 2 else ""

        result[username.lower()] = RosterEntry(
            github_username = username,
            first_name_he   = first,
            last_name_he    = last,
            email           = email,
        )

    print(f"[Roster] {len(result)} entries loaded.")
    return result


def lookup_by_github_username(
    github_username: str,
    roster: dict[str, RosterEntry] | None = None,
) -> RosterEntry | None:
    """
    Find a student in the roster by their GitHub username (case-insensitive).
    Loads the roster fresh if not provided.
    """
    if roster is None:
        roster = load_classroom_roster()
    return roster.get(github_username.lower())
