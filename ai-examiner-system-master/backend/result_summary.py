"""
result_summary.py — the SINGLE funnel that keeps the `result_summary` table in sync.

Why this exists
---------------
The admin dashboard used to download every GCS result blob for an assignment and aggregate
in Python (35 MB for assignment-3; it OOM'd instances, hence the 3Gi backend). This module
maintains a small derived table (`ResultSummary`) so the dashboard can aggregate in SQL.

The one rule
------------
`result_summary` is a DERIVED read-model. The GCS blob is the source of truth. Every place
that produces or edits a grade MUST call `upsert_summary_from_blob()` with the same dict it
writes to the blob, so the table never drifts:
  - initial grading           (main.run_grader_background)
  - regrade                    (same path)
  - appeal / manual edits      (whatever writes the blob must also call this)
If a write path forgets to call this, the table goes stale for those students only; rebuild
at any time with `scripts/backfill_result_summary.py` (it reads the blobs, the truth).

Everything here is pure + idempotent. Safe to call twice; safe to rebuild from scratch.

Wiring status (2026-07): built, not yet enabled in the live path. `run_grader_background`
calls it only when RESULT_SUMMARY_ENABLED is set, so a deploy is inert until switched on
(the OS make-up exams keep running unchanged). See MULTI_COURSE_MIGRATION §4.10.
"""
from datetime import datetime
from typing import Optional


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _duration_min(blob: dict) -> Optional[float]:
    """Best-effort exam length: start_time → last answer/question timestamp, in minutes."""
    start = _parse_dt(blob.get("start_time"))
    if not start:
        return None
    last = start
    for turn in (blob.get("transcript") or []):
        for key in ("answer_submitted_at", "question_shown_at", "llm_called_at"):
            t = _parse_dt(turn.get(key))
            if t and t > last:
                last = t
    delta = (last - start).total_seconds() / 60.0
    return round(delta, 1) if delta > 0 else None


def summary_from_blob(blob: dict) -> dict:
    """Pure transform: a result blob dict → the ResultSummary column dict.

    Accepts the exact `blob_data` built in run_grader_background, or a blob loaded back
    from GCS (same shape). Reads defensively so partial/old blobs don't crash the funnel.
    """
    fg = blob.get("final_grade") or {}
    gv = blob.get("grader_verdict") or {}
    cr = blob.get("code_review") or {}

    def _int(v):
        try:
            return int(round(float(v)))
        except (TypeError, ValueError):
            return None

    return {
        "assignment_name":      blob.get("assignment_name"),
        "github_username":      blob.get("github_username"),
        "student_id":           blob.get("student_id"),
        "full_id":              blob.get("full_id"),
        "hebrew_name":          blob.get("hebrew_name"),
        "id_resolution_status": blob.get("id_resolution_status"),
        "final_grade":          _int(fg.get("finalWeightedGrade")),
        "oral_score":           _int(fg.get("oralDefenseScore", gv.get("oralDefenseScore"))),
        "static_score":         _int(fg.get("staticCodeQualityScore", cr.get("staticCodeQualityScore"))),
        "authorship":           gv.get("authorshipAssessment"),
        "integrity_flag":       bool(gv.get("integrityFlag")) if gv.get("integrityFlag") is not None else None,
        "prompt_injection_flag": bool(gv.get("promptInjectionFlag")) if gv.get("promptInjectionFlag") is not None else None,
        "reviewer_challenged":  bool((cr.get("reviewerValidation") or {}).get("any_unfair_deductions"))
                                if cr.get("reviewerValidation") else None,
        "status":               blob.get("status"),
        "timed_out":            blob.get("timed_out"),
        "switch_used":          blob.get("switch_used"),
        "duration_min":         _duration_min(blob),
        "exam_date":            _parse_dt(blob.get("start_time")),
    }


def upsert_summary(db, row: dict) -> None:
    """Atomic INSERT-or-UPDATE of one ResultSummary row (keyed by assignment+username).

    Postgres path uses ON CONFLICT; falls back to merge() for SQLite/tests. Requires a valid
    assignment_name + github_username; silently no-ops otherwise (a half-identified blob is
    not worth a row and must not crash grading)."""
    from models import ResultSummary  # local import: keeps this module import-cheap

    if not row.get("assignment_name") or not row.get("github_username"):
        return
    row = {**row, "updated_at": datetime.utcnow()}

    dialect = db.bind.dialect.name if db.bind is not None else ""
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(ResultSummary.__table__).values(**row)
        update_cols = {c: stmt.excluded[c] for c in row
                       if c not in ("assignment_name", "github_username")}
        stmt = stmt.on_conflict_do_update(
            index_elements=["assignment_name", "github_username"],
            set_=update_cols,
        )
        db.execute(stmt)
    else:
        db.merge(ResultSummary(**row))
    db.commit()


def upsert_summary_from_blob(db, blob: dict) -> None:
    """Convenience: transform a blob and upsert it. This is the function every grade-write
    path should call."""
    upsert_summary(db, summary_from_blob(blob))
