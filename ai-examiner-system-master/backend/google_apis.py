"""
google_apis.py — Google Sheets (pre-exam survey responses) and Calendar integration.

Note: Google Forms API v1 has restrictions with service accounts on personal accounts.
We read form responses via the Google Sheets API on the linked responses spreadsheet instead.

Auth (in order of preference):
  1. Auto-detect backend/keys/ai-examiner-system-*.json  (local dev)
  2. GOOGLE_SERVICE_ACCOUNT_KEY_PATH env var → explicit path
  3. Application Default Credentials  (Cloud Run production)
"""

import os
from functools import lru_cache
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────────

# Google Sheets spreadsheet that collects pre-exam survey responses.
# Open the Form → Responses tab → Sheets icon to reach this spreadsheet.
SURVEY_SHEET_ID = "1kEN87rzbQo-aTX7vBvov41W1Z8k4GOKPq83nAeEYhZY"

# Google Sheets spreadsheet that collects post-exam survey responses (mandatory AI policy survey).
POST_SURVEY_SHEET_ID = "1h1dZXxQNfs6w72xBEN3N2RVcLilrY85PeDaEtbpP5D0"

# Exam slot sign-up calendar
CALENDAR_ID = "mtemp7875@gmail.com"

# Organiser email — excluded when parsing attendees from calendar events
_ORGANISER_EMAIL = "mtemp7875@gmail.com"

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


# ── Credentials ──────────────────────────────────────────────────────────────

def _find_key_path() -> str | None:
    keys_dir = Path(__file__).parent / "keys"
    for f in keys_dir.glob("ai-examiner-system-*.json"):
        return str(f)
    path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY_PATH", "")
    return path if path and os.path.isfile(path) else None


@lru_cache(maxsize=1)
def _credentials():
    key_path = _find_key_path()
    if key_path:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_file(key_path, scopes=_SCOPES)
    import google.auth
    creds, _ = google.auth.default(scopes=_SCOPES)
    return creds


# ── Google Sheets (survey responses) ─────────────────────────────────────────

def get_sheet_rows(sheet_range: str = "Form Responses 1") -> tuple[list[str], list[list[str]]]:
    """
    Read the linked survey responses spreadsheet.
    Returns (headers, data_rows) where headers is the first row and
    data_rows is a list of value lists (one per response).
    """
    from googleapiclient.discovery import build
    svc    = build("sheets", "v4", credentials=_credentials(), cache_discovery=False)
    result = (
        svc.spreadsheets()
           .values()
           .get(spreadsheetId=SURVEY_SHEET_ID, range=sheet_range)
           .execute()
    )
    rows = result.get("values", [])
    if not rows:
        return [], []
    headers   = rows[0]
    data_rows = rows[1:]
    return headers, data_rows


def extract_respondent_ids(
    headers: list[str],
    data_rows: list[list[str]],
    id_col_hint: str = "מספר",
) -> set[str]:
    """
    Extract normalised student IDs from survey responses.
    Finds the column whose header contains `id_col_hint` (case-insensitive).
    Returns a set of digit-only strings (9-digit preferred, 5-digit fallback).

    Call get_sheet_rows() first, then pass the results here.
    After running probe_google_apis.py you'll know the exact header name.
    """
    col_idx = next(
        (i for i, h in enumerate(headers) if id_col_hint.lower() in h.lower()),
        None,
    )
    if col_idx is None:
        print(f"[Sheets] Column containing {id_col_hint!r} not found in headers: {headers}")
        return set()

    ids: set[str] = set()
    for row in data_rows:
        if col_idx >= len(row):
            continue
        raw    = row[col_idx].strip()
        digits = "".join(c for c in raw if c.isdigit())
        if digits:
            ids.add(digits[-9:] if len(digits) >= 9 else digits[-5:])
    return ids


def _get_sheet_rows_for(sheet_id: str, sheet_range: str = "Form Responses 1") -> tuple[list[str], list[list[str]]]:
    """Read any spreadsheet by ID."""
    from googleapiclient.discovery import build
    svc    = build("sheets", "v4", credentials=_credentials(), cache_discovery=False)
    result = (
        svc.spreadsheets()
           .values()
           .get(spreadsheetId=sheet_id, range=sheet_range)
           .execute()
    )
    rows = result.get("values", [])
    if not rows:
        return [], []
    return rows[0], rows[1:]


def get_pre_survey_respondent_ids(id_col_hint: str = "תעודת זהות") -> set[str]:
    """Return normalised student IDs from the pre-exam survey responses."""
    headers, rows = _get_sheet_rows_for(SURVEY_SHEET_ID)
    return extract_respondent_ids(headers, rows, id_col_hint)


def get_post_survey_respondent_ids(id_col_hint: str | None = None) -> set[str]:
    """Return normalised student IDs from the mandatory post-exam survey responses."""
    headers, rows = _get_sheet_rows_for(POST_SURVEY_SHEET_ID)
    if id_col_hint is not None:
        return extract_respondent_ids(headers, rows, id_col_hint)
    for hint in ("תעודת זהות", "מספר", "id"):
        ids = extract_respondent_ids(headers, rows, hint)
        if ids:
            return ids
    return set()


# ── Google Calendar ───────────────────────────────────────────────────────────

def get_calendar_events(time_min: str | None = None, time_max: str | None = None) -> list[dict]:
    """
    Return calendar events. time_min / time_max are RFC3339 strings (optional).
    Each event has 'summary', 'start', 'end', 'attendees', 'description', etc.
    """
    from googleapiclient.discovery import build
    svc    = build("calendar", "v3", credentials=_credentials(), cache_discovery=False)
    params = dict(
        calendarId   = CALENDAR_ID,
        singleEvents = True,
        orderBy      = "startTime",
        maxResults   = 500,
    )
    if time_min:
        params["timeMin"] = time_min
    if time_max:
        params["timeMax"] = time_max
    return svc.events().list(**params).execute().get("items", [])


def extract_registered_emails(events: list[dict]) -> set[str]:
    """
    Return student emails from exam-slot events (excludes the organiser).
    Each event has exactly 2 attendees: organiser + student.
    """
    emails: set[str] = set()
    for ev in events:
        for att in ev.get("attendees", []):
            email = att.get("email", "").strip().lower()
            if email and email != _ORGANISER_EMAIL.lower():
                emails.add(email)
    return emails


def extract_calendar_slots(events: list[dict]) -> list[tuple[str, str]]:
    """
    Return list of (student_email, dateTime_str) for all non-organiser attendees.
    dateTime_str is the raw RFC3339 string from event.start.dateTime (or .date for all-day).
    Used for cross-referencing calendar registrations against actual exam sessions.
    """
    slots = []
    organiser = _ORGANISER_EMAIL.lower()
    for ev in events:
        start = ev.get("start", {})
        dt_str = start.get("dateTime") or start.get("date", "")
        if not dt_str:
            continue
        for att in ev.get("attendees", []):
            email = att.get("email", "").strip().lower()
            if email and email != organiser:
                slots.append((email, dt_str))
    return slots


def count_events_by_day(events: list[dict]) -> dict[str, int]:
    """
    Return {YYYY-MM-DD: count} for events that have at least one non-organiser attendee.
    Uses the event's start.dateTime (or start.date for all-day events).
    """
    by_day: dict[str, int] = {}
    organiser = _ORGANISER_EMAIL.lower()
    for ev in events:
        has_student = any(
            att.get("email", "").strip().lower() not in ("", organiser)
            for att in ev.get("attendees", [])
        )
        if not has_student:
            continue
        start = ev.get("start", {})
        dt_str = start.get("dateTime") or start.get("date", "")
        if dt_str:
            date_key = dt_str[:10]
            by_day[date_key] = by_day.get(date_key, 0) + 1
    return by_day


def count_events_by_day_and_hour(events: list[dict]) -> dict[str, dict[str, int]]:
    """
    Return {YYYY-MM-DD: {HH: count}} for events with at least one non-organiser attendee.
    Hour is extracted from dateTime's local representation (offset already in RFC3339 string).
    """
    result: dict[str, dict[str, int]] = {}
    organiser = _ORGANISER_EMAIL.lower()
    for ev in events:
        has_student = any(
            att.get("email", "").strip().lower() not in ("", organiser)
            for att in ev.get("attendees", [])
        )
        if not has_student:
            continue
        start = ev.get("start", {})
        dt_str = start.get("dateTime") or start.get("date", "")
        if not dt_str:
            continue
        date_key = dt_str[:10]
        hour_key = dt_str[11:13] if "T" in dt_str else "00"
        if date_key not in result:
            result[date_key] = {}
        result[date_key][hour_key] = result[date_key].get(hour_key, 0) + 1
    return result
