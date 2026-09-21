"""
models.py — SQLAlchemy ORM table definitions.

Tables:
  users          — maps github_username → session list
  sessions       — one row per exam session, stores all state as JSON text columns
  result_summary — one row per (assignment, github_username): the ~15 fields the admin
                   dashboard aggregates over. A DERIVED read-model — GCS result blobs remain
                   the source of truth; this table is kept in sync via result_summary.py so
                   the admin endpoint can aggregate in SQL instead of downloading every blob.
                   See docs/TECHNICAL_SPEC.md §"Admin aggregation" and MULTI_COURSE_MIGRATION §4.10.
"""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    github_username = Column(String, primary_key=True, index=True)

    sessions = relationship("Session", back_populates="user", lazy="select")


class Session(Base):
    __tablename__ = "sessions"

    session_id   = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    github_username = Column(String, ForeignKey("users.github_username"), index=True)
    start_time   = Column(DateTime, default=datetime.utcnow)

    # Lifecycle: "in-progress" → "completed" → "graded"
    status       = Column(String, default="in-progress")

    # ── Human-readable exam log ──────────────────────────────────────────────
    transcript   = Column(Text, default="[]")

    # ── Anthropic API state ──────────────────────────────────────────────────
    examiner_messages    = Column(Text, default="[]")
    picker_state         = Column(Text, default="{}")
    pending_tool_use_id  = Column(String, nullable=True)

    # ── Session metadata ─────────────────────────────────────────────────────
    turn             = Column(Integer, default=0)
    session_seed     = Column(BigInteger)
    examiner_temp    = Column(Float)

    student_files_context = Column(Text, nullable=True)
    assignment_name   = Column(String, nullable=True)
    persona           = Column(String, nullable=True)
    language          = Column(String, default="he", nullable=False)
    github_username_manual = Column(Boolean, default=False)

    # ── Timeout / switch / reask state ───────────────────────────────────────
    timed_out         = Column(Boolean, default=False)
    timeout_metadata  = Column(Text, nullable=True)
    switch_used       = Column(Boolean, default=False)
    reask_pending     = Column(Boolean, default=False)

    # ── Numeric student ID (parsed from id.txt at grading time) ─────────────
    # student_id       — 5-digit short form (last 5 of full_id, or what the student wrote)
    # full_id_from_repo — 9-digit full Israeli ID parsed from id.txt (null if student wrote 5 digits)
    # id_resolution_status — one of: ok_9_digits, ok_5_digits, missing_file, empty_file,
    #                         wrong_length, no_digits, fetch_error, ok, name_not_in_roster,
    #                         ambiguous_5_digit_match  (last three set by Phase 3 name lookup)
    # id_resolution_detail — extra context for wrong_length / fetch_error
    student_id           = Column(String, nullable=True)
    full_id_from_repo    = Column(String, nullable=True)

    # ── Course-neutral student key (MULTI_COURSE_MIGRATION §4.3c) ────────────
    # Namespaced identity that works for courses without GitHub: "gh:<username>"
    # or "id:<9 digits>". Populated on every new session; github_username is kept
    # alongside it so existing queries, the retake lock and all historical rows
    # keep working unchanged during the transition.
    # NOTE: the migration script MUST run before this model ships — SQLAlchemy will
    # SELECT this column, and a database without it errors on every session read.
    # See backend/scripts/migrate_add_student_key.py
    student_key          = Column(String, nullable=True, index=True)
    id_resolution_status = Column(String, nullable=True)
    id_resolution_detail = Column(String, nullable=True)

    # ── Grading results (filled in by background task) ───────────────────────
    final_grade      = Column(Text, nullable=True)
    professor_report = Column(Text, nullable=True)
    code_review      = Column(Text, nullable=True)
    grader_verdict   = Column(Text, nullable=True)

    # ── Email delivery tracking ──────────────────────────────────────────────
    # NULL = never sent (including freshly graded sessions)
    # True = grade email successfully delivered to student
    grade_email_sent = Column(Boolean, nullable=True)

    user = relationship("User", back_populates="sessions")


class ResultSummary(Base):
    """One row per graded (assignment, student). Derived read-model for the admin
    dashboard — populated from the same data that goes into each GCS result blob, via
    the single funnel in result_summary.py. Never the source of truth; safe to rebuild
    at any time from the blobs with scripts/backfill_result_summary.py."""
    __tablename__ = "result_summary"

    # composite identity: one graded result per student per assignment
    assignment_name  = Column(String, primary_key=True, index=True)
    github_username  = Column(String, primary_key=True, index=True)

    # identity resolution
    student_id           = Column(String, nullable=True)   # 5-digit
    full_id              = Column(String, nullable=True)   # 9-digit
    hebrew_name          = Column(String, nullable=True)
    id_resolution_status = Column(String, nullable=True)

    # grades (the numbers the dashboard averages / histograms)
    final_grade   = Column(Integer, nullable=True)
    oral_score    = Column(Integer, nullable=True)
    static_score  = Column(Integer, nullable=True)

    # integrity / authorship (flags shown in the admin table)
    authorship            = Column(String, nullable=True)   # established / partial / not_established
    integrity_flag        = Column(Boolean, nullable=True)
    prompt_injection_flag = Column(Boolean, nullable=True)
    reviewer_challenged   = Column(Boolean, nullable=True)  # validator flagged an unfair deduction (§4.9)

    # session facts
    status        = Column(String, nullable=True)     # graded / invalidated / ...
    timed_out     = Column(Boolean, nullable=True)
    switch_used   = Column(Boolean, nullable=True)
    duration_min  = Column(Float, nullable=True)
    exam_date     = Column(DateTime, nullable=True)   # session start_time

    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
