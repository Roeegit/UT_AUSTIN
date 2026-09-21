#!/usr/bin/env python3
"""
probe_classroom_roster.py — Look up a student in classroom_roster.csv.

Run from the backend/ directory:
  python scripts/probe_classroom_roster.py --username matanmarx24
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from roster_utils import load_classroom_roster, lookup_by_github_username


def run(github_username: str) -> None:
    roster = load_classroom_roster()
    entry  = lookup_by_github_username(github_username, roster)

    if not entry:
        print(f"NOT FOUND: {github_username!r} is not in the classroom roster.")
        return

    print(f"Found {github_username!r}:")
    print(f"  Hebrew name : {entry.full_name_he!r}")
    print(f"  Email       : {entry.email!r}")
    print()
    print("The production grader will match this name against id_mapping.csv on GCS.")
    print("Upload roster to GCS so production has it:")
    print("  gsutil cp backend/roster/classroom_roster.csv "
          "gs://$GCS_SUBMISSIONS_BUCKET/private/classroom_roster.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    run(args.username)
