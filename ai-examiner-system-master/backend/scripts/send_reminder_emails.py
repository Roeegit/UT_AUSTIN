#!/usr/bin/env python3
"""
send_reminder_emails.py — Send day-before exam reminder to students.

Fetches tomorrow's exam slots from Google Calendar, resolves each student's
GitHub username from the classroom roster, and emails them links to verify
their code appears in the correct GitHub repo before they sit the exam.

Run from the backend/ directory:
  python scripts/send_reminder_emails.py              # tomorrow (default)
  python scripts/send_reminder_emails.py --date 2026-05-30
  python scripts/send_reminder_emails.py --dry-run    # print, don't send
  python scripts/send_reminder_emails.py --preview-to me@example.com

Requires: SMTP_USER, SMTP_PASSWORD, GITHUB_ORG env vars.
Google credentials via ADC (Cloud Run) or GOOGLE_SERVICE_ACCOUNT_KEY_PATH.
"""

import argparse
import os
import smtplib
import ssl
import sys
from datetime import datetime, timedelta, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from google_apis import get_calendar_events, _ORGANISER_EMAIL
from roster_utils import load_classroom_roster, RosterEntry

_FROM_EMAIL = "os.biu.2026@gmail.com"
_FROM_NAME  = "מערכות הפעלה — בר-אילן"
_LOCAL_TZ   = ZoneInfo("Asia/Jerusalem")


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------

def _events_for_date(target: date) -> list[tuple[str, str]]:
    """Return [(student_email, exam_time_str)] for all slots on target date."""
    day_start = datetime(target.year, target.month, target.day, 0, 0, 0,
                         tzinfo=_LOCAL_TZ)
    day_end   = day_start + timedelta(days=1)

    events = get_calendar_events(
        time_min=day_start.isoformat(),
        time_max=day_end.isoformat(),
    )

    slots = []
    org_lower = _ORGANISER_EMAIL.lower()
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

    return slots


# ---------------------------------------------------------------------------
# Roster reverse map
# ---------------------------------------------------------------------------

def _email_to_roster(roster: dict[str, RosterEntry]) -> dict[str, RosterEntry]:
    """Return {email_lower: RosterEntry} so we can join on calendar email."""
    return {
        entry.email.strip().lower(): entry
        for entry in roster.values()
        if entry.email.strip()
    }


# ---------------------------------------------------------------------------
# Repo link construction
# ---------------------------------------------------------------------------

def _repo_links(github_username: str) -> tuple[str, str, str]:
    """
    Return (assignment1_url, assignment2_url, assignment3_url) for the student.

    Uses the same naming patterns as github_stub._resolve_repo_full_name
    without probing GitHub.  The email explains the -2 / -3 suffix variants.
    """
    org = os.environ.get("GITHUB_ORG", "").strip()
    base = f"https://github.com/{org}" if org else "https://github.com/<ORG>"

    a1 = f"{base}/biu-os-2026-assignment-1-claude-code-shell-hooks-{github_username}"
    a2 = f"{base}/assignment-2-{github_username}"
    a3 = f"{base}/assignment-3-{github_username}"
    return a1, a2, a3


# ---------------------------------------------------------------------------
# Email body
# ---------------------------------------------------------------------------

def _build_email(first_name: str, exam_time: str,
                 a1_link: str, a2_link: str, a3_link: str) -> tuple[str, str]:
    """Return (subject, plain-text body) for the reminder."""
    greeting  = f"שלום {first_name}," if first_name else "שלום,"
    time_note = f" בשעה {exam_time}" if exam_time else ""

    subject = "תזכורת: הערכת ידע אוטומטית מחר — ודאו שהקוד שלכם ב-GitHub"

    body = f"""\
{greeting}

תזכורת: מחר{time_note} תתקיים הערכת הידע האוטומטית שלכם במסגרת קורס מערכות הפעלה.

לפני הבחינה, אנא ודאו שהקוד שלכם מופיע ב-GitHub בריפוזיטורי הנכון.
זאת אחת הסיבות השכיחות לתקלות — סטודנטים שמגלים רק בזמן הבחינה שהקוד לא הועלה.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
בדקו את הקוד שלכם בלינקים הבאים:

מטלה 1:
{a1_link}

מטלה 2:
{a2_link}

מטלה 3:
{a3_link}
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
    return subject, body


# ---------------------------------------------------------------------------
# Send helper
# ---------------------------------------------------------------------------

def _send(smtp_user: str, smtp_password: str, smtp_host: str, smtp_port: int,
          to_email: str, to_name: str, subject: str, body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = formataddr((_FROM_NAME, smtp_user))
    msg["To"]      = formataddr((to_name, to_email)) if to_name else to_email
    msg.attach(MIMEText(body, "plain", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as srv:
        srv.ehlo()
        srv.starttls(context=ctx)
        srv.login(smtp_user, smtp_password)
        srv.sendmail(smtp_user, [to_email], msg.as_string())


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

def run(target: date, dry_run: bool, preview_to: str | None = None) -> None:
    tag = (f"[PREVIEW → {preview_to}]" if preview_to
           else ("[DRY RUN]" if dry_run else "[LIVE]"))

    smtp_user     = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.environ.get("SMTP_PORT", "587"))

    if not dry_run and not preview_to and (not smtp_user or not smtp_password):
        print("ERROR: SMTP_USER and SMTP_PASSWORD must be set.", file=sys.stderr)
        sys.exit(1)

    print(f"{tag} Fetching calendar events for {target} …")
    slots = _events_for_date(target)
    print(f"{tag} {len(slots)} student slot(s) found.")

    if not slots:
        print(f"{tag} No exams scheduled for {target} — nothing to send.")
        return

    print(f"{tag} Loading classroom roster …")
    roster = load_classroom_roster()
    by_email = _email_to_roster(roster)

    sent = skipped = errors = 0

    for calendar_email, exam_time in slots:
        print(f"\n{tag}  email={calendar_email}  time={exam_time}")

        entry = by_email.get(calendar_email)
        if entry:
            github_username = entry.github_username
            first_name      = entry.first_name_he
            print(f"       ↳ github={github_username}  name={entry.full_name_he}")
        else:
            github_username = "<your-github-username>"
            first_name      = ""
            print(f"       ↳ not in roster — using placeholder username in links")

        a1_link, a2_link, a3_link = _repo_links(github_username)
        subject, body    = _build_email(first_name, exam_time, a1_link, a2_link, a3_link)

        dest = preview_to if preview_to else calendar_email
        print(f"       To: {dest}")

        if dry_run:
            print("  --- email body ---")
            print(body)
            print("  ---")
            sent += 1
            continue

        try:
            _send(smtp_user, smtp_password, smtp_host, smtp_port,
                  dest, first_name, subject, body)
            print("       Sent.")
            sent += 1
        except Exception as exc:
            print(f"       ERROR: {exc}")
            errors += 1

        if preview_to:
            print(f"       Preview done — stopping after first.")
            break

    print(f"\n{tag} Done.  sent={sent}  skipped={skipped}  errors={errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send day-before exam reminders.")
    parser.add_argument(
        "--date", metavar="YYYY-MM-DD", default=None,
        help="Target exam date (default: tomorrow in Asia/Jerusalem)",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print emails without sending")
    parser.add_argument("--preview-to", metavar="EMAIL",
                        help="Send one real email to this address to preview rendering")
    args = parser.parse_args()

    target_date = (
        date.fromisoformat(args.date)
        if args.date
        else (datetime.now(_LOCAL_TZ) + timedelta(days=1)).date()
    )

    run(target=target_date, dry_run=args.dry_run, preview_to=args.preview_to)
