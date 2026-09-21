#!/usr/bin/env python3
"""
migrate_add_grade_email_sent.py — One-time migration: add grade_email_sent column.

Run once from the backend/ directory after deploying the models.py change:
  python scripts/migrate_add_grade_email_sent.py

Safe to run multiple times (checks for column existence first).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Check if column already exists
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='sessions' AND column_name='grade_email_sent'"
    ))
    if result.fetchone():
        print("Column grade_email_sent already exists — nothing to do.")
    else:
        conn.execute(text(
            "ALTER TABLE sessions ADD COLUMN grade_email_sent BOOLEAN"
        ))
        conn.commit()
        print("Column grade_email_sent added to sessions table.")
