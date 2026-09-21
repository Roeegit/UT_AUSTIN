#!/usr/bin/env python3
"""
backfill_result_summary.py — (re)build the `result_summary` table from the GCS result blobs.

The blobs are the source of truth; this reconstructs the derived table from them. Safe to run
any time — it upserts, so re-running is idempotent. Use it for the initial backfill and any
time the table is suspected stale (e.g. after appeal edits that bypassed the funnel).

Run from the backend/ directory:
  python scripts/backfill_result_summary.py --dry-run                 # print, write nothing
  python scripts/backfill_result_summary.py --assignment assignment-3 # one assignment, live
  python scripts/backfill_result_summary.py                           # all assignments, live
  python scripts/backfill_result_summary.py --local-dir C:/tmp/blobs/a3 --sqlite out.db
        # offline test: read local blob files, write to a throwaway SQLite (no GCS, no Cloud SQL)

Reads each blob, runs the SAME transform (result_summary.summary_from_blob) the live grader
uses, and upserts. Invalidated blobs are recorded too (status='invalidated') so the dashboard
can exclude them consistently.
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


def _load(path_or_text: str) -> dict:
    txt = path_or_text.lstrip("﻿").lstrip()
    return json.JSONDecoder().raw_decode(txt)[0]


def _iter_local(local_dir: str):
    for fp in sorted(glob.glob(os.path.join(local_dir, "*.json"))):
        try:
            yield _load(open(fp, encoding="utf-8-sig").read())
        except Exception as exc:  # noqa: BLE001
            print(f"  [skip] {os.path.basename(fp)}: {exc}")


def _iter_gcs(assignment_filter):
    from github_stub import _gcs_client
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        sys.exit("GCS_SUBMISSIONS_BUCKET not set")
    bucket = _gcs_client.bucket(bucket_name)
    prefixes = [f"results/{assignment_filter}/"] if assignment_filter else ["results/"]
    for prefix in prefixes:
        for blob in bucket.list_blobs(prefix=prefix):
            if not blob.name.endswith(".json"):
                continue
            try:
                yield _load(blob.download_as_text())
            except Exception as exc:  # noqa: BLE001
                print(f"  [skip] {blob.name}: {exc}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assignment", help="restrict to one assignment_name")
    ap.add_argument("--dry-run", action="store_true", help="print rows, write nothing")
    ap.add_argument("--local-dir", help="read blob files from a local dir instead of GCS")
    ap.add_argument("--sqlite", help="write to a throwaway SQLite file instead of the live DB")
    args = ap.parse_args()

    from result_summary import summary_from_blob, upsert_summary

    # choose a DB session
    db = None
    if not args.dry_run:
        if args.sqlite:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from database import Base
            import models  # noqa: F401  (register tables on Base)
            engine = create_engine(f"sqlite:///{args.sqlite}")
            Base.metadata.create_all(engine, tables=[models.ResultSummary.__table__])
            db = sessionmaker(bind=engine)()
        else:
            from database import SessionLocal
            db = SessionLocal()

    source = _iter_local(args.local_dir) if args.local_dir else _iter_gcs(args.assignment)

    n, by_assign = 0, {}
    for blob in source:
        if args.assignment and blob.get("assignment_name") != args.assignment:
            continue
        row = summary_from_blob(blob)
        if not row.get("github_username"):
            continue
        n += 1
        by_assign[row["assignment_name"]] = by_assign.get(row["assignment_name"], 0) + 1
        if args.dry_run:
            print(f"  {row['assignment_name']:30} {row['github_username']:20} "
                  f"final={row['final_grade']} oral={row['oral_score']} static={row['static_score']} "
                  f"auth={row['authorship']} status={row['status']} dur={row['duration_min']}")
        else:
            upsert_summary(db, row)

    print(f"\n{'[DRY RUN] would upsert' if args.dry_run else 'upserted'} {n} rows")
    for a, c in sorted(by_assign.items()):
        print(f"  {a}: {c}")
    if db:
        db.close()


if __name__ == "__main__":
    main()
