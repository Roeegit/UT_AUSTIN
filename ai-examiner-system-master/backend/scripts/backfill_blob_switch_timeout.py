"""
Backfill switch_used and timeout_metadata into existing GCS result blobs.

Reads both fields from Cloud SQL (source of truth) and patches any blob
that is missing either field.  Blobs with status='invalidated' are skipped.

Auth: uses your active `gcloud auth` session — no ADC setup required.
Run from the backend/ directory:
    python scripts/backfill_blob_switch_timeout.py
    python scripts/backfill_blob_switch_timeout.py --dry-run
"""

import argparse
import json
import os
import subprocess
import sys

# On Windows gcloud is a batch script, not a bare executable
_GCLOUD = "gcloud.cmd" if sys.platform == "win32" else "gcloud"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── GCS auth via dev service-account key ────────────────────────────────────
_KEY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "keys", "ai-examiner-system-fdb2ddaa78ca.json")
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", _KEY)

# ── DB auth via gcloud access token ─────────────────────────────────────────
os.environ.setdefault("CLOUD_SQL_INSTANCE", "ai-examiner-system:me-west1:ai-exam-db")
os.environ.setdefault("DB_USER",            "examuser")
os.environ.setdefault("DB_NAME",            "postgres")
os.environ.setdefault("DB_PASS",            "OSNoymanSagui26")
os.environ.setdefault("GCS_SUBMISSIONS_BUCKET", subprocess.check_output(
    [_GCLOUD, "secrets", "versions", "access", "latest",
     "--secret=GCS_SUBMISSIONS_BUCKET", "--project=ai-examiner-system"],
    text=True, shell=(sys.platform == "win32"),
).strip())


def _get_gcloud_credentials():
    from google.oauth2.credentials import Credentials
    token = subprocess.check_output(
        [_GCLOUD, "auth", "print-access-token", "--account=sarne.lab@gmail.com"],
        text=True, shell=(sys.platform == "win32"),
    ).strip()
    return Credentials(token)


def main(dry_run: bool) -> None:
    # ── Connect to DB ────────────────────────────────────────────────────────
    from google.cloud.sql.connector import Connector
    import sqlalchemy

    creds = _get_gcloud_credentials()
    connector = Connector(credentials=creds)

    def _getconn():
        return connector.connect(
            os.environ["CLOUD_SQL_INSTANCE"],
            "pg8000",
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
            db=os.environ["DB_NAME"],
        )

    engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=_getconn)

    with engine.connect() as conn:
        rows = conn.execute(sqlalchemy.text("""
            SELECT github_username, assignment_name, switch_used, timeout_metadata
            FROM sessions
            WHERE status IN ('graded', 'complaint_pending')
              AND github_username IS NOT NULL
              AND assignment_name IS NOT NULL
        """)).fetchall()

    print(f"[DB] Found {len(rows)} graded/complaint sessions.")

    # ── Patch GCS blobs (reuse same gcloud token) ────────────────────────────
    from google.cloud import storage as gcs

    gcs_client = gcs.Client(credentials=creds, project="ai-examiner-system")
    bucket = gcs_client.bucket(os.environ["GCS_SUBMISSIONS_BUCKET"])

    patched = skipped = missing = errors = 0

    for row in rows:
        username     = row[0]
        assignment   = row[1]
        switch_used  = row[2]       # bool or None
        timeout_meta = row[3]       # str (JSON) or None

        blob_path = f"results/{assignment}/{username}.json"
        blob = bucket.blob(blob_path)

        try:
            data = json.loads(blob.download_as_text())
        except Exception as exc:
            print(f"  [MISS] {blob_path}: {exc}")
            missing += 1
            continue

        if data.get("status") == "invalidated":
            skipped += 1
            continue

        # Only patch if at least one field is missing from the blob
        needs_patch = ("switch_used" not in data) or ("timeout_metadata" not in data)
        if not needs_patch:
            skipped += 1
            continue

        data["switch_used"]      = bool(switch_used) if switch_used is not None else False
        data["timeout_metadata"] = json.loads(timeout_meta) if timeout_meta else {}

        if dry_run:
            print(f"  [DRY] would patch {blob_path}  switch_used={data['switch_used']}")
        else:
            blob.upload_from_string(
                json.dumps(data, ensure_ascii=False, indent=2),
                content_type="application/json; charset=utf-8",
            )
            print(f"  [OK]  patched {blob_path}")
        patched += 1

    connector.close()
    print(f"\nDone. patched={patched}  skipped={skipped}  blob_missing={missing}  errors={errors}")
    if dry_run:
        print("(dry-run — no changes written)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print what would change without writing")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
