"""
schemas.py — Pydantic request / response models for the FastAPI endpoints.
"""
from typing import Any, List, Optional
from pydantic import BaseModel


# ── POST /api/admin/fetch-submission ─────────────────────────────────────────

class FetchSubmissionRequest(BaseModel):
    github_username: str
    assignment_name: str = "test-assignment"


class FetchSubmissionResponse(BaseModel):
    github_username: str
    repo:            str
    files_saved:     list[str]
    files_missing:   list[str]
    message:         str


# ── POST /api/auth/start ─────────────────────────────────────────────────────

class StartRequest(BaseModel):
    github_username: str
    assignment_name: Optional[str] = None
    persona: Optional[str] = None
    language: Optional[str] = "he"
    github_username_manual: Optional[bool] = False


class StartResponse(BaseModel):
    session_id: str
    question_text: str
    question_number: int
    message: str = "Exam started. Good luck!"
    action: Optional[str] = None
    action_file: Optional[str] = None
    action_code_line: Optional[str] = None
    assignment_name: Optional[str] = None
    files: Optional[dict[str, str]] = None
    exam_duration_seconds: int = 960


# ── POST /api/exam/answer ────────────────────────────────────────────────────

class AnswerRequest(BaseModel):
    session_id: str
    student_answer: str


class AnswerResponse(BaseModel):
    finished: bool
    question_text: Optional[str] = None
    question_number: Optional[int] = None
    message: Optional[str] = None
    chosen_difficulty:      Optional[str] = None
    next_difficulty_signal: Optional[str] = None
    understanding_score:    Optional[float] = None
    authorship_confidence:  Optional[str] = None
    internal_reasoning:     Optional[str] = None
    offered_topics: Optional[List[Any]] = None
    switch_granted: Optional[bool] = None
    action: Optional[str] = None
    action_file: Optional[str] = None
    action_code_line: Optional[str] = None
    distress_ended: Optional[bool] = None


# ── POST /api/exam/timeout ────────────────────────────────────────────────────

class TimeoutRequest(BaseModel):
    session_id: str
    partial_answer: Optional[str] = None


class TimeoutResponse(BaseModel):
    status: str
    questions_answered: int
    questions_timed_out: int


# ── POST /api/admin/invalidate-session ───────────────────────────────────────

class InvalidateSessionRequest(BaseModel):
    session_id:      Optional[str] = None
    github_username: Optional[str] = None
    assignment_name: Optional[str] = None
    reason:          Optional[str] = None
    # Which status to set. "retake_enabled" = just let the student sit again
    # (default); "invalidated" = the exam didn't go through, discard the sitting.
    # Both unlock the retake — see RETAKE_UNLOCKING_STATUSES in main.py.
    new_status:      str = "retake_enabled"


class InvalidateSessionResponse(BaseModel):
    invalidated_sessions: list[str]
    github_username:      Optional[str] = None
    reason:               Optional[str] = None


# ── POST /api/admin/resend-grade-emails ──────────────────────────────────────

class ResendGradeEmailsRequest(BaseModel):
    assignment: str
    usernames:  list[str]
    # Optional per-call connection-error bonus (make-good for a technical disruption,
    # e.g. a disconnection). Applied to every username in this call, on top of the
    # adaptation/REPORT bonuses, capped at 100. 0 = none.
    connection_bonus: int = 0


# ── GET /api/exam/lookup/{github_username} ────────────────────────────────────

class AssignmentOption(BaseModel):
    name:       str
    label_he:   str
    label_en:   str


class LookupResponse(BaseModel):
    found:                  bool
    locked:                 bool = False
    github_username:        str
    assignment_name:        Optional[str] = None
    assignment_label_he:    Optional[str] = None
    assignment_label_en:    Optional[str] = None
    available_assignments:  Optional[list[AssignmentOption]] = None
    error:                  Optional[str] = None


# ── POST /api/exam/complaint ─────────────────────────────────────────────────

class ComplaintRequest(BaseModel):
    session_id:      Optional[str] = None
    github_username: Optional[str] = None
    contact_name:    str
    contact_info:    str
    note:            Optional[str] = None


class ComplaintResponse(BaseModel):
    status:     str
    session_id: str


# ── GET /api/admin/results/{github_username} ──────────────────────────────────

class SessionSummary(BaseModel):
    session_id: str
    start_time: str
    status: str
    final_grade: Optional[Any] = None
    professor_report: Optional[str] = None
    transcript: Any = None
    code_review: Optional[Any] = None
    grader_verdict: Optional[Any] = None


class ResultsResponse(BaseModel):
    github_username: str
    sessions: list[SessionSummary]


# ── POST /api/exam/preview ────────────────────────────────────────────────────

class PreviewRequest(BaseModel):
    github_username: str
    assignment_name: Optional[str] = None


class PreviewResponse(BaseModel):
    files: dict[str, str]
    fetched: bool
