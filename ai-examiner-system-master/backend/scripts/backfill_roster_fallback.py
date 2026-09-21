#!/usr/bin/env python3
"""
backfill_roster_fallback.py — Apply classroom-roster ID fallback to already-graded
sessions where id.txt was missing or unresolvable.

Run from the backend/ directory:
  python scripts/backfill_roster_fallback.py [--dry-run]

What it does:
  For every graded session whose id_resolution_status is one of
  (missing_file, empty_file, no_digits, wrong_length, fetch_error, name_not_in_roster):
    1. Look up github_username in classroom_roster.csv
    2. Match the Hebrew name against id_mapping.csv  (via _by_name reverse map)
    3. If resolved: update DB row + rewrite GCS result blob
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

FALLBACK_STATUSES = {
    "missing_file", "empty_file", "no_digits",
    "wrong_length", "fetch_error", "name_not_in_roster",
}


def run(dry_run: bool) -> None:
    from database import SessionLocal
    from models import Session as ExamSession
    from roster_utils import load_classroom_roster, lookup_by_github_username
    from main import _load_id_mapping, _by_name, _ID_MAP_LOCK
    import main as _main
    from github_stub import _gcs_client

    tag = "[DRY RUN]" if dry_run else "[LIVE]"

    # Load the two lookup tables
    print(f"{tag} Loading id_mapping...")
    _load_id_mapping()
    print(f"{tag} Loading classroom roster...")
    roster = load_classroom_roster()

    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    bucket      = _gcs_client.bucket(bucket_name) if bucket_name else None

    db = SessionLocal()
    try:
        sessions = (
            db.query(ExamSession)
            .filter(
                ExamSession.status == "graded",
                ExamSession.id_resolution_status.in_(list(FALLBACK_STATUSES)),
            )
            .all()
        )
        print(f"{tag} Found {len(sessions)} session(s) with unresolved IDs.\n")

        resolved = skipped = 0

        for s in sessions:
            print(f"{tag} github={s.github_username}  "
                  f"assignment={s.assignment_name}  status={s.id_resolution_status}")

            entry = lookup_by_github_username(s.github_username or "", roster)
            if not entry:
                print(f"       → not in classroom roster, skipping.")
                skipped += 1
                continue

            with _main._ID_MAP_LOCK:
                full_id = _main._by_name.get(entry.full_name_he)

            if not full_id:
                print(f"       → roster name {entry.full_name_he!r} not in id_mapping, skipping.")
                skipped += 1
                continue

            print(f"       → resolved: {entry.full_name_he!r}  full_id={full_id!r}")
            if dry_run:
                resolved += 1
                continue

            # Update DB
            s.full_id_from_repo    = full_id
            s.student_id           = full_id[-5:]
            s.id_resolution_status = "ok_via_classroom_roster"
            s.id_resolution_detail = f"roster:{entry.full_name_he}"
            db.commit()

            # Rewrite GCS blob
            if bucket:
                blob_path = f"results/{s.assignment_name}/{s.github_username}.json"
                try:
                    existing = json.loads(bucket.blob(blob_path).download_as_text())
                    existing.update({
                        "full_id":              full_id,
                        "full_id_from_repo":    full_id,
                        "student_id":           full_id[-5:],
                        "hebrew_name":          entry.full_name_he,
                        "id_resolution_status": "ok_via_classroom_roster",
                        "id_resolution_detail": f"roster:{entry.full_name_he}",
                    })
                    bucket.blob(blob_path).upload_from_string(
                        json.dumps(existing, ensure_ascii=False, indent=2),
                        content_type="application/json; charset=utf-8",
                    )
                    print(f"       → blob updated: {blob_path}")
                except Exception as e:
                    print(f"       → blob update failed: {e}")

            resolved += 1

    finally:
        db.close()

    print(f"\n{tag} Done. resolved={resolved}  skipped={skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
