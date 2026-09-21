#!/usr/bin/env python3
"""
send_grades.py — Send grade emails to students after the AI oral exam.

Run from the backend/ directory:
  python scripts/send_grades.py --unsent          # only sessions not yet emailed
  python scripts/send_grades.py --all             # all graded sessions (re-sends too)
  python scripts/send_grades.py --unsent --dry-run  # preview without sending

Flags:
  --unsent    Send only to sessions where grade_email_sent IS NULL (default mode)
  --all       Send to all graded sessions (including already-sent ones)
  --dry-run   Print what would be sent, write nothing

Requirements:
  - Same env vars as the backend (CLOUD_SQL_INSTANCE, DB_USER, DB_PASS, DB_NAME,
    GCS_SUBMISSIONS_BUCKET, SMTP_USER, SMTP_PASSWORD)
  - Student email mapping: private/student_emails.csv on GCS (full_id,email,group)
"""

import argparse
import json
import os
import smtplib
import ssl
import sys
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


def _load_email_map(bucket) -> tuple[dict[str, str], dict[str, str]]:
    """
    Load student_emails.csv from GCS.
    Returns (full_id → email, last5 → email).
    last5 index only includes unambiguous mappings (one entry per suffix).
    """
    import csv, io
    mapping: dict[str, str] = {}
    last5_counts: dict[str, int] = {}
    last5_map: dict[str, str] = {}
    try:
        text = bucket.blob("private/student_emails.csv").download_as_text(encoding="utf-8-sig")
        for row in csv.DictReader(io.StringIO(text)):
            full_id = (row.get("full_id") or "").strip()
            email   = (row.get("email") or "").strip()
            if full_id and email:
                mapping[full_id] = email
                suffix = full_id[-5:] if len(full_id) >= 5 else full_id
                last5_counts[suffix] = last5_counts.get(suffix, 0) + 1
                last5_map[suffix] = email
        # Remove ambiguous suffixes (more than one full_id shares them)
        last5_map = {k: v for k, v in last5_map.items() if last5_counts[k] == 1}
        print(f"[Email map] Loaded {len(mapping)} entries, {len(last5_map)} unambiguous last-5 entries.")
    except Exception as exc:
        print(f"[Email map] Could not load student_emails.csv: {exc}")
    return mapping, last5_map


def _resolve_email(
    blob_data: dict,
    email_map: dict[str, str],
    last5_map: dict[str, str],
) -> tuple[str | None, str]:
    """
    Resolve a student email using a multi-tier fallback chain:
      1. full_id (resolved by grading pipeline) → student_emails.csv
      2. full_id_from_repo (raw from id.txt) → student_emails.csv
      3. student_id (last-5) → student_emails.csv (unambiguous only)
      4. github_username → classroom roster email
    Returns (email_or_None, method_description).
    """
    # Tier 1 & 2 — full 9-digit ID
    for id_field in ("full_id", "full_id_from_repo"):
        fid = (blob_data.get(id_field) or "").strip()
        if fid and fid in email_map:
            return email_map[fid], id_field

    # Tier 3 — last-5 suffix (unambiguous)
    sid = (blob_data.get("student_id") or "").strip()
    if sid and sid in last5_map:
        return last5_map[sid], "last5_match"

    # Tier 4 — classroom roster by github_username
    try:
        from roster_utils import lookup_by_github_username
        entry = lookup_by_github_username(blob_data.get("github_username") or "")
        if entry and getattr(entry, "email", None):
            return entry.email.strip(), "roster"
    except Exception:
        pass

    return None, "not_found"


def _send_email(smtp_user: str, smtp_password: str, smtp_host: str, smtp_port: int,
                to_addr: str, subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = smtp_user
    msg["To"]      = to_addr

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls(context=context)
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_addr, msg.as_string())


def run(mode: str, dry_run: bool, preview_to: str | None = None) -> None:
    from database import SessionLocal
    from models import Session as ExamSession
    from github_stub import _gcs_client
    from grade_email_template import build_grade_email, validate_email_readiness

    if preview_to:
        tag = f"[PREVIEW → {preview_to}]"
    elif dry_run:
        tag = "[DRY RUN]"
    else:
        tag = "[LIVE]"

    smtp_user     = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    smtp_host     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.environ.get("SMTP_PORT", "587"))

    if not dry_run and (not smtp_user or not smtp_password):
        print("ERROR: SMTP_USER and SMTP_PASSWORD must be set.", file=sys.stderr)
        sys.exit(1)

    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        print("ERROR: GCS_SUBMISSIONS_BUCKET is not set.", file=sys.stderr)
        sys.exit(1)

    bucket    = _gcs_client.bucket(bucket_name)
    email_map, last5_map = _load_email_map(bucket)

    db = SessionLocal()
    try:
        query = db.query(ExamSession).filter(ExamSession.status == "graded")
        if mode == "unsent":
            query = query.filter(ExamSession.grade_email_sent.isnot(True))

        sessions = query.all()
        print(f"{tag} Mode={mode!r}  Found {len(sessions)} session(s) to process.")

        sent = skipped = errors = 0

        for i, s in enumerate(sessions, 1):
            print(f"\n{tag} [{i}/{len(sessions)}]  github={s.github_username}  "
                  f"assignment={s.assignment_name}  full_id={s.full_id_from_repo!r}")

            # ── Load GCS blob for grade data (needed for email resolution too) ─
            blob_path = f"results/{s.assignment_name}/{s.github_username}.json"
            try:
                blob_data = json.loads(bucket.blob(blob_path).download_as_text())
            except Exception as exc:
                print(f"  ERROR loading blob {blob_path}: {exc}")
                errors += 1
                continue

            # ── Resolve student email ────────────────────────────────────────
            if preview_to:
                student_email = preview_to  # override recipient for preview
            else:
                student_email, method = _resolve_email(blob_data, email_map, last5_map)
                if not student_email:
                    print(f"  SKIP — no email address found (full_id={s.full_id_from_repo!r}, student_id={blob_data.get('student_id')!r})")
                    skipped += 1
                    continue
                print(f"  Email resolved via: {method}")

            # ── Validate email readiness ─────────────────────────────────────
            validation = validate_email_readiness(blob_data)
            if not validation["is_valid"]:
                print(f"  SKIP — email not ready. Missing: {validation['missing_fields']}")
                skipped += 1
                continue

            # ── Build email ──────────────────────────────────────────────────
            subject, body = build_grade_email(blob_data)
            print(f"  To: {student_email}")
            print(f"  Subject: {subject}")

            if dry_run:
                print("  --- email body preview (first 400 chars) ---")
                print(body[:400])
                print("  ---")
                sent += 1
                continue

            # ── Send ─────────────────────────────────────────────────────────
            try:
                _send_email(smtp_user, smtp_password, smtp_host, smtp_port,
                            student_email, subject, body)
                print(f"  Sent.")
            except Exception as exc:
                print(f"  ERROR sending email: {exc}")
                errors += 1
                continue

            if preview_to:
                # Preview send: do not mark as sent, stop after first email
                print(f"  Preview sent to {preview_to} — not marking session as sent.")
                sent += 1
                break

            # ── Mark sent in DB ───────────────────────────────────────────────
            s.grade_email_sent = True
            db.commit()

            # ── Update blob ───────────────────────────────────────────────────
            try:
                blob_data["grade_email_sent"] = True
                bucket.blob(blob_path).upload_from_string(
                    json.dumps(blob_data, ensure_ascii=False, indent=2),
                    content_type="application/json; charset=utf-8",
                )
            except Exception as exc:
                print(f"  WARNING: DB updated but blob update failed: {exc}")

            sent += 1

    finally:
        db.close()

    print(f"\n{tag} Done.  sent={sent}  skipped={skipped}  errors={errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send grade emails to students.")
    group  = parser.add_mutually_exclusive_group()
    group.add_argument("--unsent", action="store_true",
                       help="Send only to sessions not yet emailed (default)")
    group.add_argument("--all", action="store_true",
                       help="Send to all graded sessions, including already-sent")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview emails without sending or marking sent")
    parser.add_argument("--preview-to", metavar="EMAIL",
                        help="Send one real email to this address (not the student) "
                             "to preview rendering. Does not mark any session as sent.")
    args = parser.parse_args()

    mode = "all" if args.all else "unsent"
    run(mode=mode, dry_run=args.dry_run, preview_to=args.preview_to)
