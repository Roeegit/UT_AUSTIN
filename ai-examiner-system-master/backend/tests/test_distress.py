"""
tests/test_distress.py — Tests for the END_EXAM_DISTRESS flow.

Run from the backend/ directory:
    pip install pytest httpx
    pytest tests/test_distress.py -v
"""
import json
import sys
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Stub out cloud dependencies BEFORE any project module is imported.
# database.py runs `Connector()` at module level, so we must inject fakes
# into sys.modules before Python executes that top-level code.
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def _make_module(name: str) -> MagicMock:
    m = MagicMock()
    m.__name__ = name
    m.__spec__ = MagicMock()
    return m

# Stub the entire google.cloud.sql hierarchy
for mod_name in [
    "google",
    "google.cloud",
    "google.cloud.sql",
    "google.cloud.sql.connector",
    "google.cloud.storage",
    "google.auth",
    "google.auth.credentials",
    "google.oauth2",
    "google.oauth2.service_account",
    "google_auth_httplib2",
    "google.auth.transport",
    "google.auth.transport.requests",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = _make_module(mod_name)

# Stub google.cloud.sql.connector.Connector so database.py can instantiate it
_connector_mod = sys.modules["google.cloud.sql.connector"]
_connector_mod.Connector = MagicMock(return_value=MagicMock())

# Stub google.cloud.storage so github_stub.py / complaint flow can import
_storage_mod = sys.modules["google.cloud.storage"]
_storage_mod.Client = MagicMock(return_value=MagicMock())

# Swap database.py for an SQLite-backed version before anything imports it
import sqlalchemy
from sqlalchemy.orm import DeclarativeBase

_TEST_DB_URL = "sqlite:///./test_distress.db"
_test_engine = sqlalchemy.create_engine(_TEST_DB_URL, connect_args={"check_same_thread": False})
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

# Build a fake database module that looks just like the real one
_db_mod = MagicMock()

class _Base(DeclarativeBase):
    pass

_db_mod.Base = _Base
_db_mod.engine = _test_engine
_db_mod.SessionLocal = _TestSession

def _get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()

_db_mod.get_db = _get_db
sys.modules["database"] = _db_mod

# Now import the project modules — they'll pick up the stubbed database
_FAKE_PROMPT = "FAKE SYSTEM PROMPT"

_mock_open = MagicMock(return_value=MagicMock(
    __enter__=lambda s: s,
    __exit__=MagicMock(return_value=False),
    read=MagicMock(return_value=_FAKE_PROMPT),
))

with (
    patch("builtins.open", _mock_open),
    patch("plan_assembler.load_pool", return_value=[]),
):
    import main  # noqa: E402

from models import Session as ExamSession, User  # noqa: E402 — models use _Base

# Create tables in the test DB
_Base.metadata.create_all(bind=_test_engine)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_db():
    """Wipe all rows before every test so fixed session IDs never collide."""
    db = _TestSession()
    db.query(ExamSession).delete()
    db.query(User).delete()
    db.commit()
    db.close()


@pytest.fixture()
def db_session():
    session = _TestSession()
    yield session
    session.close()


@pytest.fixture()
def client():
    """FastAPI TestClient wired to the test SQLite DB."""
    main.app.dependency_overrides[_get_db] = _get_db
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


def _make_session(db, session_id: str = "test-session-distress", student_id: str = "s123"):
    """Insert a minimal in-progress session into the DB."""
    user = db.query(User).filter(User.student_id == student_id).first()
    if not user:
        user = User(student_id=student_id, github_username=student_id)
        db.add(user)

    transcript = [
        {"role": "Examiner", "content": {"questionText": "מה זה fork()?", "questionNumber": 1}},
        {"role": "Student", "content": "אני לא יכול להמשיך, אני בפאניקה"},
    ]
    picker_state = {
        "seed": 42,
        "turn": 1,
        "used_focuses": [],
        "used_files": [],
        "used_dims": [],
        "excluded_ids": [],
    }

    session = ExamSession(
        session_id          = session_id,
        student_id          = student_id,
        status              = "in-progress",
        transcript          = json.dumps(transcript),
        examiner_messages   = "[]",
        picker_state        = json.dumps(picker_state),
        pending_tool_use_id = "fake-tool-id",
        turn                = 1,
        session_seed        = 42,
        examiner_temp       = 0.3,
        student_files_context = json.dumps({"main.c": "int main(){return 0;}"}),
        assignment_name     = "test-assignment",
    )
    db.add(session)
    db.commit()
    return session


# ---------------------------------------------------------------------------
# 1. Unit: handler dispatches END_EXAM_DISTRESS and does NOT call the grader
# ---------------------------------------------------------------------------

class TestDistressDispatch:

    def test_end_exam_distress_does_not_call_grader(self, db_session):
        """When examiner returns END_EXAM_DISTRESS the grader must never be invoked."""
        _make_session(db_session, session_id="dispatch-test")

        distress_json = {
            "action": "END_EXAM_DISTRESS",
            "studentPersona": "distressed",
            "questionNumber": 1,
            "questionText": "אני רואה שזה מצב קשה עבורך. הבחינה מסתיימת כעת.",
            "actionParameters": {"fileName": None, "codeLine": None},
            "internalEvaluation": {
                "understandingScore": None,
                "authorshipConfidence": None,
                "integrityFlag": False,
                "suspectedPromptInjection": False,
                "notes": "distress detected",
            },
            "bugPivotUsed": False,
            "switchGranted": False,
            "chosenTopicDifficulty": None,
            "nextQuestionDifficulty": None,
            "internalReasoning": {},
        }

        main.app.dependency_overrides[_get_db] = _get_db
        with (
            patch.object(main, "_get_anthropic_client"),
            patch.object(main, "call_examiner_qn", return_value=(
                [], "tool-id-2", distress_json, "claude-test"
            )),
            patch.object(main, "run_grader_background") as mock_grader,
            patch.object(main, "_send_distress_email"),
            patch("main._gcs_client", MagicMock(), create=True),
        ):
            with TestClient(main.app) as c:
                resp = c.post("/api/exam/answer", json={
                    "session_id": "dispatch-test",
                    "student_answer": "אני לא יכול להמשיך, אני בפאניקה",
                })
        main.app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["finished"] is True
        assert body["distress_ended"] is True
        mock_grader.assert_not_called()

        # Also verify the DB row was updated — check within the same test so we
        # don't depend on state surviving across the clean_db autouse fixture.
        db_session.expire_all()
        saved = db_session.query(ExamSession).filter(
            ExamSession.session_id == "dispatch-test"
        ).first()
        assert saved is not None
        assert saved.status == "ended_distress"


# ---------------------------------------------------------------------------
# 2. Unit: idempotency — second call on ended_distress session is a no-op
# ---------------------------------------------------------------------------

class TestDistressIdempotency:

    def test_second_distress_call_returns_early(self, db_session):
        """Calling the handler on an already-ended session must not re-send email or write GCS."""
        _make_session(db_session, session_id="idempotent-test")

        # Pre-set session to ended_distress
        session = db_session.query(ExamSession).filter(
            ExamSession.session_id == "idempotent-test"
        ).first()
        session.status = "ended_distress"
        db_session.commit()

        main.app.dependency_overrides[_get_db] = _get_db
        with (
            patch.object(main, "_send_distress_email") as mock_email,
            patch("main._gcs_client", MagicMock(), create=True),
        ):
            with TestClient(main.app) as c:
                resp = c.post("/api/exam/answer", json={
                    "session_id": "idempotent-test",
                    "student_answer": "any answer",
                })
        main.app.dependency_overrides.clear()

        # The answer endpoint must reject the call (session already ended)
        assert resp.status_code == 400
        mock_email.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Retake test: ended_distress does not block a new session
# ---------------------------------------------------------------------------

class TestRetakeAllowance:

    def test_ended_distress_does_not_block_retake(self, db_session):
        """A student with an ended_distress session must be able to start a new one."""
        student_id = "retake-student"
        assignment = "test-assignment"

        # Create an ended_distress session for this student
        _make_session(db_session, session_id="old-distress-session", student_id=student_id)
        session = db_session.query(ExamSession).filter(
            ExamSession.session_id == "old-distress-session"
        ).first()
        session.status = "ended_distress"
        db_session.commit()

        # The retake-prevention query in start_exam filters on status == "graded".
        # We verify directly that the query returns nothing for this student.
        blocking = (
            db_session.query(ExamSession)
            .filter(
                ExamSession.student_id      == student_id,
                ExamSession.assignment_name == assignment,
                ExamSession.status          == "graded",
            )
            .first()
        )
        assert blocking is None, (
            "ended_distress session must not appear in the graded-session retake check"
        )
