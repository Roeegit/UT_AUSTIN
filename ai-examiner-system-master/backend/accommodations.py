"""
accommodations.py — Extended-time accommodation check.

Students on the accommodation list get EXTENDED_TIME_SECONDS instead of the
default exam duration.  The list lives in:
  GCS:   private/extended_time_ids.txt   (production)
  Local: backend/roster/extended_time_ids.txt  (dev)

Each line is a 9-digit Israeli national ID.  Students who only submit 5 digits
in id.txt are matched against the last-5 suffix of every entry.
"""

import os
from functools import lru_cache
from pathlib import Path

EXTENDED_TIME_SECONDS = 19 * 60   # 1140 s = 19 minutes
_GCS_PATH   = "private/extended_time_ids.txt"
_LOCAL_PATH = Path(__file__).parent.parent / "private-data" / "extended_time_ids.txt"


@lru_cache(maxsize=1)
def _load_ids() -> frozenset[str]:
    """Load the accommodation ID set from GCS or local file (9-digit IDs)."""
    raw = _read_raw()
    ids: set[str] = set()
    for line in raw.splitlines():
        digits = "".join(c for c in line if c.isdigit())
        if digits:
            ids.add(digits[-9:] if len(digits) >= 9 else digits)
    return frozenset(ids)


def _read_raw() -> str:
    bucket = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if bucket:
        try:
            from github_stub import _gcs_client
            return _gcs_client.bucket(bucket).blob(_GCS_PATH).download_as_text(encoding="utf-8")
        except Exception as exc:
            print(f"[Accommodations] GCS load failed ({exc}), trying local...")
    if _LOCAL_PATH.exists():
        return _LOCAL_PATH.read_text(encoding="utf-8")
    print(f"[Accommodations] File not found at {_LOCAL_PATH} or GCS — no extended-time students.")
    return ""


def is_extended_time(id_raw: str) -> bool:
    """
    Return True if the student's ID (raw string from id.txt) is on the
    accommodation list.  Handles both 9-digit full IDs and 5-digit short forms.
    """
    digits = "".join(c for c in id_raw if c.isdigit())
    if not digits:
        return False
    full_ids = _load_ids()
    if len(digits) >= 9:
        return digits[-9:] in full_ids
    # Short form (≤8 digits): match against suffix of every full ID
    suffix = digits[-5:] if len(digits) >= 5 else digits
    return any(fid.endswith(suffix) for fid in full_ids)
