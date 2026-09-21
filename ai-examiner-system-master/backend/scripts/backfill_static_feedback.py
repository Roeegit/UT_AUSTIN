#!/usr/bin/env python3
"""
backfill_static_feedback.py — Re-run the code reviewer for graded sessions that
are missing the `studentStaticFeedback` field in their code_review JSON.

Run from the backend/ directory:
  python scripts/backfill_static_feedback.py [--dry-run] [--assignment ASSIGNMENT_NAME]

What it does:
  For every graded session whose stored code_review JSON lacks `studentStaticFeedback`:
    1. Reconstruct the student_files dict from student_files_context (already in DB)
    2. Call the code reviewer with the updated prompt
    3. Update DB (session.code_review) and GCS blob
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


def run(dry_run: bool, assignment_filter: str | None, force: bool = False) -> None:
    from database import SessionLocal
    from models import Session as ExamSession
    from agents import call_code_reviewer
    from main import _get_anthropic_client, _get_assignment_resources, CODE_REVIEWER_PROMPT
    from github_stub import _gcs_client

    tag = "[DRY RUN]" if dry_run else "[LIVE]"

    client = _get_anthropic_client()
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    bucket = _gcs_client.bucket(bucket_name) if bucket_name else None

    db = SessionLocal()
    try:
        query = db.query(ExamSession).filter(ExamSession.status == "graded")
        if assignment_filter:
            query = query.filter(ExamSession.assignment_name == assignment_filter)
        sessions = query.all()

        candidates = []
        for s in sessions:
            try:
                cr = json.loads(s.code_review or "{}")
            except (json.JSONDecodeError, TypeError):
                cr = {}
            if force or "studentStaticFeedback" not in cr:
                candidates.append(s)

        label = "to rerun" if force else "missing studentStaticFeedback"
        print(f"{tag} Found {len(candidates)} session(s) {label}.\n")

        updated = skipped = errors = 0

        for s in candidates:
            print(f"{tag} {s.github_username}  assignment={s.assignment_name}")

            # Reconstruct files dict from DB
            raw = s.student_files_context or ""
            try:
                files_dict = json.loads(raw) if raw.startswith("{") else {}
            except json.JSONDecodeError:
                files_dict = {"submission.c": raw} if raw else {}

            if not files_dict:
                print(f"       → no student_files_context stored, skipping.")
                skipped += 1
                continue

            if dry_run:
                print(f"       → would re-run code reviewer ({len(files_dict)} file(s))")
                updated += 1
                continue

            try:
                _, assignment_readme = _get_assignment_resources(s.assignment_name or "test-assignment")
                new_cr, model_used = call_code_reviewer(
                    client, CODE_REVIEWER_PROMPT, assignment_readme, files_dict
                )
                print(f"       → code reviewer done (model={model_used}, "
                      f"score={new_cr.get('staticCodeQualityScore')}, "
                      f"feedback={'yes' if new_cr.get('studentStaticFeedback') else 'MISSING'})")

                # Update DB
                s.code_review = json.dumps(new_cr, ensure_ascii=False)
                db.commit()

                # Update GCS blob
                if bucket:
                    blob_path = f"results/{s.assignment_name}/{s.github_username}.json"
                    try:
                        existing = json.loads(bucket.blob(blob_path).download_as_text())
                        existing["code_review"] = new_cr
                        bucket.blob(blob_path).upload_from_string(
                            json.dumps(existing, ensure_ascii=False, indent=2),
                            content_type="application/json; charset=utf-8",
                        )
                        print(f"       → blob updated: {blob_path}")
                    except Exception as e:
                        print(f"       → blob update failed: {e}")

                updated += 1

            except Exception as e:
                print(f"       → ERROR: {e}")
                db.rollback()
                errors += 1

    finally:
        db.close()

    print(f"\n{tag} Done. updated={updated}  skipped={skipped}  errors={errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--assignment", default=None, help="Limit to one assignment name")
    parser.add_argument("--force", action="store_true",
                        help="Re-run code reviewer even for sessions that already have "
                             "studentStaticFeedback (e.g. to upgrade from Sonnet to Opus)")
    args = parser.parse_args()
    run(dry_run=args.dry_run, assignment_filter=args.assignment, force=args.force)
