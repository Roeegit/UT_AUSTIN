"""
send_post_survey_reminder.py — Remind students who haven't filled the mandatory post-survey.

Checks all graded sessions for the given assignments, compares against post-survey
respondents from Google Sheets, and emails anyone who hasn't filled it.

Usage (run from backend/):
  python scripts/send_post_survey_reminder.py --dry-run
  python scripts/send_post_survey_reminder.py

The script uses the same email resolution chain as send_grades.py:
  full_id → student_emails.csv → last-5 suffix → classroom roster.
"""

import argparse
import json
import os
import smtplib
import ssl
import subprocess
import sys
import tempfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

_GCLOUD = "gcloud.cmd" if sys.platform == "win32" else "gcloud"
_BUCKET = "ai-exam-submission"


def _gcs_ls(prefix: str) -> list[str]:
    """List GCS object names under prefix using gcloud CLI."""
    result = subprocess.run(
        [_GCLOUD, "storage", "ls", f"gs://{_BUCKET}/{prefix}"],
        capture_output=True, text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip().endswith(".json")]


def _gcs_download_json(gs_uri: str) -> dict | None:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        subprocess.run([_GCLOUD, "storage", "cp", gs_uri, tmp],
                       check=True, capture_output=True)
        with open(tmp, encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as exc:
        print(f"  WARN: could not load {gs_uri}: {exc}")
        return None
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass

ASSIGNMENTS = [
    "biu-os-2026-assignment-1-claude-code-shell-hooks",
    "assignment-2",
    "assignment-3",
]

POST_SURVEY_URL = "https://docs.google.com/forms/d/e/1FAIpQLScgjuaK3HC1QObG2BTR8ga4ROyTNz8KCTdywfcL9zGcMfgYPg/viewform"

SUBJECT = "תזכורת — מילוי סקר AI (חובה)"

def _build_body(name: str) -> str:
    return f"""\
שלום {name},

לפי הרישומים שלנו, טרם מילאת את סקר ה-AI שנשלח לאחר בחינת ההגנה.

מילוי הסקר הוא חלק חובה מדרישות הקורס ויש להשלימו בהקדם:
{POST_SURVEY_URL}

בברכה,
צוות הקורס — מערכות הפעלה, אוניברסיטת בר-אילן

---
זהו מייל אוטומטי, אין להשיב אליו.
"""


def run(dry_run: bool) -> None:
    from send_grades import _resolve_email

    smtp_user     = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.environ.get("SMTP_PORT", "587"))

    if not dry_run and (not smtp_user or not smtp_password):
        print("ERROR: SMTP_USER and SMTP_PASSWORD must be set.", file=sys.stderr)
        sys.exit(1)

    # ── Load email map from GCS via gcloud CLI ─────────────────────────────
    import csv, io, tempfile
    email_map: dict[str, str] = {}
    last5_map: dict[str, str] = {}
    last5_counts: dict[str, int] = {}
    try:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            tmp_csv = f.name
        subprocess.run([_GCLOUD, "storage", "cp",
                        f"gs://{_BUCKET}/private/student_emails.csv", tmp_csv],
                       check=True, capture_output=True)
        with open(tmp_csv, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                fid   = (row.get("full_id") or "").strip()
                email = (row.get("email") or "").strip()
                if fid and email:
                    email_map[fid] = email
                    suffix = fid[-5:] if len(fid) >= 5 else fid
                    last5_counts[suffix] = last5_counts.get(suffix, 0) + 1
                    last5_map[suffix] = email
        last5_map = {k: v for k, v in last5_map.items() if last5_counts[k] == 1}
        os.unlink(tmp_csv)
        print(f"[Email map] {len(email_map)} entries loaded.")
    except Exception as exc:
        print(f"WARN: could not load student_emails.csv: {exc}")

    # ── Load post-survey respondents from local CSV ────────────────────────
    import csv as _csv
    survey_csv = Path(r"C:\Users\Shachar\Desktop\שאלון אחרי הבדיקה -AI (Responses) - Form Responses 1.csv")
    print(f"Loading post-survey respondents from {survey_csv.name} ...")
    post_survey_ids: set[str] = set()
    try:
        with open(survey_csv, encoding="utf-8-sig") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                raw_id = (row.get("תעודת זהות") or "").strip().replace("-", "").replace(" ", "")
                if raw_id.isdigit():
                    post_survey_ids.add(raw_id)          # full ID (9-digit)
                    post_survey_ids.add(raw_id[-5:])     # last-5 suffix for partial matches
        print(f"  {len(post_survey_ids)//2} respondents found (stored as full + last-5).")
    except Exception as exc:
        print(f"ERROR loading post-survey CSV: {exc}", file=sys.stderr)
        sys.exit(1)

    def _already_filled(blob: dict) -> bool:
        sid      = (blob.get("student_id") or "").strip()
        full_id  = (blob.get("full_id") or blob.get("full_id_from_repo") or "").strip()
        if not sid and not full_id:
            return False
        return any(
            (sid and (sid in resp_id or resp_id in full_id))
            for resp_id in post_survey_ids
        )

    # ── Scan graded blobs across both assignments ──────────────────────────
    to_remind: list[dict] = []

    for assignment in ASSIGNMENTS:
        prefix = f"results/{assignment}/"
        print(f"\nScanning {assignment}...")
        uris = _gcs_ls(prefix)
        print(f"  {len(uris)} result blob(s) found.")

        for uri in uris:
            data = _gcs_download_json(uri)
            if data is None:
                continue

            if data.get("status") not in ("graded",):
                continue
            if not data.get("grade_email_sent"):
                # Student hasn't received their grade yet — skip for now
                continue
            if _already_filled(data):
                continue

            student_email, method = _resolve_email(data, email_map, last5_map)
            if not student_email:
                print(f"  SKIP (no email) — {data.get('github_username')} "
                      f"full_id={data.get('full_id')!r} student_id={data.get('student_id')!r}")
                continue

            to_remind.append({
                "email":      student_email,
                "name":       data.get("hebrew_name") or data.get("github_username", "סטודנט"),
                "github":     data.get("github_username"),
                "assignment": assignment,
                "method":     method,
            })

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Total to remind: {len(to_remind)}")

    sent = errors = 0
    for i, student in enumerate(to_remind, 1):
        body = _build_body(student["name"])
        print(f"\n[{i}/{len(to_remind)}] {student['github']} ({student['assignment']})"
              f"  → {student['email']}  [via {student['method']}]")
        if dry_run:
            print(f"  Subject: {SUBJECT}")
            print(f"  Body preview: {body[:120].strip()}...")
            continue

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = SUBJECT
            msg["From"]    = smtp_user
            msg["To"]      = student["email"]
            msg.attach(MIMEText(body, "plain", "utf-8"))

            ctx = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.login(smtp_user, smtp_password)
                s.sendmail(smtp_user, student["email"], msg.as_string())
            print("  Sent.")
            sent += 1
        except Exception as exc:
            print(f"  ERROR: {exc}")
            errors += 1

    print(f"\nDone. sent={sent}  errors={errors}  skipped_no_email={len(to_remind) - sent - errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print who would be emailed without actually sending.")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
