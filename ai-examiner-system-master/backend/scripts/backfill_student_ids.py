#!/usr/bin/env python3
"""
backfill_student_ids.py — Fetch id.txt for existing graded sessions that have
no student_id yet, update the DB rows, and rewrite the GCS result blobs.

Run manually from the backend/ directory:
  python scripts/backfill_student_ids.py [--dry-run]

Flags:
  --dry-run   Print what would change without writing anything.

Requirements: same env vars as the backend (CLOUD_SQL_INSTANCE, DB_USER,
DB_PASS, DB_NAME, GCS_SUBMISSIONS_BUCKET).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Allow importing from backend/ root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


def _parse_id_txt(content, error):
    """Mirror of main.py's _parse_id_txt — kept in sync manually."""
    if error == "404":
        return None, None, "missing_file", None
    if error is not None:
        return None, None, "fetch_error", error[:200]
    if not content or not content.strip():
        return None, None, "empty_file", None
    digits = re.sub(r"\D", "", content)
    if not digits:
        return None, None, "no_digits", None
    if len(digits) == 9:
        return digits[-5:], digits, "ok_9_digits", None
    if len(digits) == 5:
        return digits, None, "ok_5_digits", None
    return None, None, "wrong_length", f"found {len(digits)} digits"


def run(dry_run: bool) -> None:
    from database import SessionLocal
    from models import Session as ExamSession
    from github_stub import fetch_single_file, _gcs_client

    mode = "[DRY RUN]" if dry_run else "[LIVE]"
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name and not dry_run:
        print("ERROR: GCS_SUBMISSIONS_BUCKET is not set.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        sessions = (
            db.query(ExamSession)
            .filter(
                ExamSession.status == "graded",
                ExamSession.student_id == None,  # noqa: E711
            )
            .all()
        )
        print(f"{mode} Found {len(sessions)} graded session(s) with no student_id.")

        for i, s in enumerate(sessions, 1):
            print(f"\n{mode} [{i}/{len(sessions)}] session={s.session_id}  github={s.github_username}  assignment={s.assignment_name}")

            content, error = fetch_single_file(
                s.github_username or "",
                s.assignment_name or "test-assignment",
                "id.txt",
            )
            numeric_sid, full_id, status, detail = _parse_id_txt(content, error)
            print(f"  id.txt: status={status!r}  student_id={numeric_sid!r}  full_id={full_id!r}  detail={detail!r}")

            if dry_run:
                continue

            # Update DB
            s.student_id           = numeric_sid
            s.full_id_from_repo    = full_id
            s.id_resolution_status = status
            s.id_resolution_detail = detail
            db.commit()
            print(f"  DB updated.")

            # Rewrite GCS blob
            if bucket_name and s.final_grade:
                try:
                    bucket = _gcs_client.bucket(bucket_name)
                    blob_path = f"results/{s.assignment_name}/{s.github_username}.json"
                    existing_blob = bucket.blob(blob_path)

                    # Load existing blob if present; otherwise build from scratch
                    try:
                        existing_data = json.loads(existing_blob.download_as_text())
                    except Exception:
                        existing_data = {}

                    # Merge updated id fields
                    existing_data.update({
                        "student_id":           numeric_sid,
                        "full_id_from_repo":    full_id,
                        "id_resolution_status": status,
                        "id_resolution_detail": detail,
                        # Ensure core fields are populated if this is a fresh build
                        "session_id":      existing_data.get("session_id", s.session_id),
                        "github_username": existing_data.get("github_username", s.github_username),
                        "assignment_name": existing_data.get("assignment_name", s.assignment_name),
                        "status":          "graded",
                        "final_grade":     existing_data.get("final_grade") or json.loads(s.final_grade or "null"),
                        "professor_report": existing_data.get("professor_report") or s.professor_report,
                        "code_review":     existing_data.get("code_review") or json.loads(s.code_review or "null"),
                        "grader_verdict":  existing_data.get("grader_verdict") or json.loads(s.grader_verdict or "null"),
                        "transcript":      existing_data.get("transcript") or json.loads(s.transcript or "[]"),
                    })

                    existing_blob.upload_from_string(
                        json.dumps(existing_data, ensure_ascii=False, indent=2),
                        content_type="application/json; charset=utf-8",
                    )
                    print(f"  GCS blob updated: {blob_path}")
                except Exception as gcs_err:
                    print(f"  GCS blob update failed: {gcs_err}")

    finally:
        db.close()

    print(f"\n{mode} Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill student_id from id.txt for graded sessions.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would change, write nothing.")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
