"""
tests/test_timeout_metadata.py — Unit tests for timeout categorisation logic.

Run from the backend/ directory:
    pytest tests/test_timeout_metadata.py -v
"""
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Stub cloud dependencies before any project module is imported.
def _make_module(name: str) -> MagicMock:
    m = MagicMock()
    m.__name__ = name
    m.__spec__ = MagicMock()
    return m

for mod_name in [
    "google", "google.cloud", "google.cloud.sql", "google.cloud.sql.connector",
    "google.cloud.storage", "google.auth", "google.auth.credentials",
    "google.oauth2", "google.oauth2.service_account", "google_auth_httplib2",
    "google.auth.transport", "google.auth.transport.requests",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = _make_module(mod_name)

sys.modules["google.cloud.sql.connector"].Connector = MagicMock(return_value=MagicMock())
sys.modules["google.cloud.storage"].Client = MagicMock(return_value=MagicMock())

# Redirect database.py to SQLite before main.py loads
import sqlalchemy
from sqlalchemy.orm import DeclarativeBase

_sqlite_engine = sqlalchemy.create_engine("sqlite:///:memory:")

class _Base(DeclarativeBase):
    pass

_fake_db_module = MagicMock()
_fake_db_module.Base   = _Base
_fake_db_module.engine = _sqlite_engine
_fake_db_module.get_db = MagicMock()
sys.modules["database"] = _fake_db_module

# Stub heavy optional deps
for mod_name in ["anthropic", "PyPDF2", "github", "httpx", "smtplib"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = _make_module(mod_name)

from main import _build_timeout_metadata  # noqa: E402


class TestTimeoutMetadataWithPartial:
    """Timeout fires on a question where the student had typed something."""

    def test_partial_on_q3_answered_includes_q3(self):
        meta = _build_timeout_metadata(timed_out_at_question=3, partial_captured=True)
        assert 3 in meta["questions_answered"]

    def test_partial_on_q3_not_in_not_reached(self):
        meta = _build_timeout_metadata(timed_out_at_question=3, partial_captured=True)
        assert 3 not in meta["questions_not_reached"]

    def test_partial_on_q3_in_questions_partial(self):
        meta = _build_timeout_metadata(timed_out_at_question=3, partial_captured=True)
        assert meta["questions_partial"] == [3]

    def test_partial_on_q3_not_reached_is_empty(self):
        # Q3 is the last question — nothing after it
        meta = _build_timeout_metadata(timed_out_at_question=3, partial_captured=True)
        assert meta["questions_not_reached"] == []

    def test_partial_on_q2_answered_is_1_and_2(self):
        meta = _build_timeout_metadata(timed_out_at_question=2, partial_captured=True)
        assert meta["questions_answered"] == [1, 2]
        assert meta["questions_partial"] == [2]
        assert meta["questions_not_reached"] == [3]

    def test_no_overlap_between_buckets_with_partial(self):
        meta = _build_timeout_metadata(timed_out_at_question=3, partial_captured=True)
        answered = set(meta["questions_answered"])
        not_reached = set(meta["questions_not_reached"])
        assert answered.isdisjoint(not_reached), "A question must not appear in both buckets"

    def test_all_questions_accounted_for_with_partial(self):
        meta = _build_timeout_metadata(timed_out_at_question=2, partial_captured=True)
        all_qs = set(meta["questions_answered"]) | set(meta["questions_not_reached"])
        assert all_qs == {1, 2, 3}


class TestTimeoutMetadataWithoutPartial:
    """Timeout fires on a question where the student hadn't started typing."""

    def test_no_partial_on_q3_not_reached_includes_q3(self):
        meta = _build_timeout_metadata(timed_out_at_question=3, partial_captured=False)
        assert 3 in meta["questions_not_reached"]

    def test_no_partial_on_q3_answered_excludes_q3(self):
        meta = _build_timeout_metadata(timed_out_at_question=3, partial_captured=False)
        assert 3 not in meta["questions_answered"]

    def test_no_partial_questions_partial_is_empty(self):
        meta = _build_timeout_metadata(timed_out_at_question=3, partial_captured=False)
        assert meta["questions_partial"] == []

    def test_no_partial_on_q2_answered_is_only_q1(self):
        meta = _build_timeout_metadata(timed_out_at_question=2, partial_captured=False)
        assert meta["questions_answered"] == [1]
        assert meta["questions_not_reached"] == [2, 3]

    def test_no_overlap_between_buckets_without_partial(self):
        meta = _build_timeout_metadata(timed_out_at_question=2, partial_captured=False)
        answered = set(meta["questions_answered"])
        not_reached = set(meta["questions_not_reached"])
        assert answered.isdisjoint(not_reached)

    def test_all_questions_accounted_for_without_partial(self):
        meta = _build_timeout_metadata(timed_out_at_question=2, partial_captured=False)
        all_qs = set(meta["questions_answered"]) | set(meta["questions_not_reached"])
        assert all_qs == {1, 2, 3}


class TestTimeoutMetadataCleanSession:
    """
    A session that completed normally (no timeout) would never call
    _build_timeout_metadata, but we verify edge-case inputs are sane:
    timed_out_at_question=3 with no partial is the closest equivalent
    to "finished just before the last question".
    """

    def test_partial_flag_preserved_in_output(self):
        meta = _build_timeout_metadata(timed_out_at_question=3, partial_captured=True)
        assert meta["partial_answer_captured"] is True

    def test_no_partial_flag_preserved_in_output(self):
        meta = _build_timeout_metadata(timed_out_at_question=3, partial_captured=False)
        assert meta["partial_answer_captured"] is False

    def test_timed_out_at_question_preserved(self):
        meta = _build_timeout_metadata(timed_out_at_question=2, partial_captured=False)
        assert meta["timed_out_at_question"] == 2

    def test_questions_partial_is_subset_of_questions_answered(self):
        meta = _build_timeout_metadata(timed_out_at_question=3, partial_captured=True)
        assert set(meta["questions_partial"]).issubset(set(meta["questions_answered"]))
