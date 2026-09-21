#!/usr/bin/env python3
"""
probe_google_apis.py — Dump raw Sheets (survey responses) and Calendar events.

Run from the backend/ directory:
  python scripts/probe_google_apis.py --sheets     # column headers + first 2 responses
  python scripts/probe_google_apis.py --calendar   # first 5 calendar events
  python scripts/probe_google_apis.py              # both (default)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import google_apis


def _probe_one_sheet(label: str, sheet_id: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"GOOGLE SHEETS — {label}  (id={sheet_id})")
    print("=" * 60)
    headers, rows = google_apis._get_sheet_rows_for(sheet_id)
    print(f"\nTotal responses: {len(rows)}")
    print(f"\nColumn headers ({len(headers)}):")
    for i, h in enumerate(headers):
        print(f"  [{i}] {h!r}")

    print(f"\nFirst 2 rows (raw values):")
    for row in rows[:2]:
        for i, val in enumerate(row):
            header = headers[i] if i < len(headers) else f"col{i}"
            print(f"  [{i}] {header!r}: {val!r}")
        print()

    for hint in ("תעודת זהות", "מספר", "id"):
        ids = google_apis.extract_respondent_ids(headers, rows, hint)
        if ids:
            print(f"Extracted IDs with hint {hint!r}: {len(ids)} IDs — sample: {list(ids)[:5]}")
            break
    else:
        print("No IDs extracted with any hint.")


def probe_sheets() -> None:
    _probe_one_sheet("pre-survey", google_apis.SURVEY_SHEET_ID)
    _probe_one_sheet("post-survey", google_apis.POST_SURVEY_SHEET_ID)


def probe_calendar() -> None:
    print("=" * 60)
    print("GOOGLE CALENDAR — exam slot events")
    print("=" * 60)
    events = google_apis.get_calendar_events()
    print(f"\nTotal events: {len(events)}")

    registered = google_apis.extract_registered_emails(events)
    print(f"Unique student emails registered: {len(registered)}")

    print(f"\nFirst 5 events:")
    for ev in events[:5]:
        attendees = [
            a.get("email") for a in ev.get("attendees", [])
            if a.get("email") != google_apis._ORGANISER_EMAIL
        ]
        print(f"  {ev.get('start', {}).get('dateTime', '?')[:16]}  "
              f"{ev.get('summary', '?')!r}  student={attendees}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheets",   action="store_true")
    parser.add_argument("--calendar", action="store_true")
    args = parser.parse_args()

    run_all = not args.sheets and not args.calendar
    try:
        if args.sheets or run_all:
            probe_sheets()
    except Exception as exc:
        print(f"[Sheets] ERROR: {exc}", file=sys.stderr)
        import traceback; traceback.print_exc()

    try:
        if args.calendar or run_all:
            probe_calendar()
    except Exception as exc:
        print(f"[Calendar] ERROR: {exc}", file=sys.stderr)
        import traceback; traceback.print_exc()
