"""One-off: rename GreenPepper139's assignment from the short name to the full name."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_KEY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "keys", "ai-examiner-system-fdb2ddaa78ca.json")
os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", _KEY)

os.environ.setdefault("CLOUD_SQL_INSTANCE", "ai-examiner-system:me-west1:ai-exam-db")
os.environ.setdefault("DB_USER",            "examuser")
os.environ.setdefault("DB_NAME",            "postgres")
os.environ.setdefault("DB_PASS",            "OSNoymanSagui26")

from database import SessionLocal
from models import Session as ExamSession

db = SessionLocal()
try:
    rows = (
        db.query(ExamSession)
        .filter(
            ExamSession.github_username == "GreenPepper139",
            ExamSession.assignment_name == "biu-os-2026-assignment-1",
        )
        .all()
    )
    if not rows:
        print("No matching sessions found — nothing to update.")
    else:
        for s in rows:
            print(f"Updating session {s.session_id}  status={s.status}")
            s.assignment_name = "biu-os-2026-assignment-1-claude-code-shell-hooks"
        db.commit()
        print(f"Done — updated {len(rows)} session(s).")
finally:
    db.close()
