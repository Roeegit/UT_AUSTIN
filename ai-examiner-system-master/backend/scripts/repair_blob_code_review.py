#!/usr/bin/env python3
"""
repair_blob_code_review.py — Sync code_review from DB into GCS blobs for sessions
where the DB has studentStaticFeedback but the blob does not.

Run from the backend/ directory:
  python scripts/repair_blob_code_review.py [--dry-run]
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


def run(dry_run: bool) -> None:
    from database import SessionLocal
    from models import Session as ExamSession
    from github_stub import _gcs_client

    tag = "[DRY RUN]" if dry_run else "[LIVE]"

    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    bucket = _gcs_client.bucket(bucket_name) if bucket_name else None

    db = SessionLocal()
    try:
        sessions = db.query(ExamSession).filter(ExamSession.status == "graded").all()

        for s in sessions:
            try:
                db_cr = json.loads(s.code_review or "{}")
            except (json.JSONDecodeError, TypeError):
                db_cr = {}

            has_in_db   = bool((db_cr.get("studentStaticFeedback") or "").strip())

            blob_cr = {}
            if bucket:
                blob_path = f"results/{s.assignment_name}/{s.github_username}.json"
                try:
                    existing = json.loads(bucket.blob(blob_path).download_as_text())
                    blob_cr = existing.get("code_review") or {}
                except Exception as e:
                    print(f"  {s.github_username}: could not read blob — {e}")
                    continue

            has_in_blob = bool((blob_cr.get("studentStaticFeedback") or "").strip())

            print(f"{s.github_username}: DB={'✓' if has_in_db else '✗'}  blob={'✓' if has_in_blob else '✗'}")

            if has_in_db and not has_in_blob:
                print(f"  → DB has feedback but blob is missing it — will repair")
                if not dry_run and bucket:
                    try:
                        blob_path = f"results/{s.assignment_name}/{s.github_username}.json"
                        existing = json.loads(bucket.blob(blob_path).download_as_text())
                        existing["code_review"] = db_cr
                        bucket.blob(blob_path).upload_from_string(
                            json.dumps(existing, ensure_ascii=False, indent=2),
                            content_type="application/json; charset=utf-8",
                        )
                        print(f"  → blob repaired: {blob_path}")
                    except Exception as e:
                        print(f"  → blob repair FAILED: {e}")

            elif not has_in_db and not has_in_blob:
                print(f"  → neither DB nor blob has feedback — needs backfill_static_feedback.py")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
