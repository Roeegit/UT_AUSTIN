"""
config.py — All paths and constants for the backend.
Edit ASSIGNMENT_NAME when switching assignments.
"""
import os

# Resolve paths relative to this file so the backend works from any CWD
_BACKEND_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROMPTS_DIR  = os.path.join(_BACKEND_DIR, "prompts")
_ASSIGN_DIR   = os.path.join(_BACKEND_DIR, "assignments")
ASSIGN_DIR    = _ASSIGN_DIR   # public alias for use in main.py

# ── Assignment ──────────────────────────────────────────────────────────────
ASSIGNMENT_NAME = "biu-os-2026-assignment-1-claude-code-shell-hooks"
STUDENT_FILES   = ["backup.c", "file_processor.c", "gladiator.c", "tournament.c"]

# Per-assignment file lists — used when loading from GCS.
# Falls back to STUDENT_FILES if an assignment isn't listed here.
ASSIGNMENT_FILES: dict[str, list[str]] = {
    "austin_a": ["failed", "accepted"],
    "test-assignment": ["backup.c", "file_processor.c", "gladiator.c", "tournament.c"],
    "qa_assignment":   ["taskexec.c", "utils.c", "utils.h"],
    "biu-os-2026-assignment-1-claude-code-shell-hooks": [
  "hook_runner.sh",
  "hooks_config.txt",
  "test.sh",
  ".env",
  ".claude/settings.json",
  ".claude/hooks/pre_command_firewall.sh",
  ".claude/hooks/pre_rate_limiter.sh",
  ".claude/hooks/pre_commit_validator.sh",
  ".claude/hooks/post_auto_backup.sh",
  ".claude/hooks/post_syntax_checker.sh",
  ".claude/hooks/post_session_summary.sh",
  ".claude/hooks/pre_secrets_guard.sh",
  ".claude/hooks/config/dangerous_patterns.txt",
  ".claude/hooks/config/hooks.conf",
  ".claude/hooks/config/commit_prefixes.txt",
  ".claude/hooks/config/secret_files.txt",
  ".claude/hooks/data/session_test-session-1.log",
  "id.txt"
],
    "assignment-2": [
  "src/part1.c",
  "src/part2.c",
  "src/part3.c",
  "src/Makefile",
  "REPORT.md",
  "id.txt",
],
    # assignment-3 spec does not require id.txt; identity is resolved from the
    # github username at grading time, so it is intentionally NOT listed here
    # (keeps the examiner from seeing a [NOT SUBMITTED] id.txt for everyone).
    "assignment-3": [
  "ex3.c",
  "Focus-Mode.c",
  "CPU-Scheduler.c",
],
}
MAX_ANSWER_CHARS = 1500

# ── Multi-assignment routing ─────────────────────────────────────────────────
# When no required_students map entry is found for a student, fall back to this.
DEFAULT_ASSIGNMENT = "assignment-2"

# The latest assignment every student must take. Once a student has a *graded*
# session for their required earlier assignment, lookup_github defaults them here
# (graded-gated routing). It stays selectable for everyone on the confirm screen.
LATEST_ASSIGNMENT = "assignment-3"

# Per-assignment GitHub repo patterns.  If an assignment isn't listed here the
# global GITHUB_REPO_PATTERN env var is used as the fallback.
ASSIGNMENT_REPO_PATTERNS: dict[str, str] = {
    "assignment-2": "assignment-2-{github_username}",
    "assignment-3": "assignment-3-{github_username}",
}

# Human-readable labels for each assignment (used in lookup response + frontend).
ASSIGNMENT_LABELS: dict[str, dict[str, str]] = {
    "austin-a": {"he": "Problem A Delta", "en": "Problem A Delta"},
    "biu-os-2026-assignment-1-claude-code-shell-hooks": {"he": "מטלה 1", "en": "Assignment 1"},
    "assignment-2":                                      {"he": "מטלה 2", "en": "Assignment 2"},
    "assignment-3":                                      {"he": "מטלה 3", "en": "Assignment 3"},
    "linear-algebra/hw1":                                {"he": "תרגיל בית 1", "en": "Homework 1"},
    # Assignments the course actually examines orally are 3, 7 and 9-10.
    "linear-algebra/hw3":                                {"he": "תרגיל בית 3", "en": "Homework 3"},
}

# Canonical list of real (non-QA) assignments that students are routed to.
KNOWN_ASSIGNMENTS: list[str] = [
    "austin-a",
    "biu-os-2026-assignment-1-claude-code-shell-hooks",
    "assignment-2",
    "assignment-3",
]

# Assignments in this set skip the retake block and GitHub fetch.
# Used for QA testing so testers can run multiple exams and files come from GCS directly.
QA_ASSIGNMENTS: set[str] = {"qa_assignment", "austin-a"}

# ── Test identities exempt from the one-time-use lock ────────────────────────
# A real student gets one sitting until an admin clears it. These identifiers may sit any
# assignment repeatedly, so staff can run dry-runs — including out of hours — without someone
# hand-enabling a retake each time.
#
# They must be identifiers no real student can hold. University IDs are nine digits and are
# issued in real ranges, so these use an obviously synthetic 12345678x pattern; each still
# needs a matching submission uploaded through the normal form for the exam to have anything
# to examine. Their sessions land in the database and the dashboard like any other, so keep
# the list short and delete it when the course goes live.
UNLIMITED_RETAKE_IDS: set[str] = {
    "123456780",
    "123456781",
    "123456782",
}


def is_unlimited_retake(identifier: str) -> bool:
    """True for a test identity that may re-sit without an admin clearing the previous run.
    Accepts either the raw identifier or a namespaced student_key ("id:123456780")."""
    raw = (identifier or "").strip()
    if raw.startswith(("gh:", "id:")):
        raw = raw[3:]
    return raw in UNLIMITED_RETAKE_IDS

# ── Google Forms submission intake (forms_stub.py) ───────────────────────────
# Assignments served by a Google Form instead of GitHub Classroom. Anything NOT
# listed here keeps going to GitHub, so the two run side by side.
#
# TWO SHAPES ARE SUPPORTED, and the difference is only in config:
#
#   one form per assignment  — omit assignment_column/assignment_value. Separate deadlines
#                              and a separate sheet each time; a new sheet to create and
#                              share with the service account for every assignment.
#   one form per COURSE      — set assignment_column/assignment_value. Students get one
#                              link for the whole semester, staff share one sheet and one
#                              Drive folder once, and each entry below picks its own rows
#                              out of the shared sheet by the dropdown answer.
#
#   sheet_id           the Form's linked responses spreadsheet
#   tab                worksheet name; None = first tab
#   id_column          header of the column holding the 9-digit university ID
#   name_column        header of the name field. Optional, but where a course keeps no
#                      roster this is the ONLY source of the student's name — it reaches
#                      the grade email and the staff report. Omit it and everyone shows up
#                      as name_not_in_roster with a nameless email (MIGRATION §4.4a).
#   assignment_column  header of the "which assignment" dropdown, on a shared form
#   assignment_value   the dropdown option that means THIS assignment. Must match the
#                      option text exactly; rows answering anything else are ignored.
#   files              {sheet column header: filename to store it as}. The stored name
#                      comes from here, never from Drive — Forms appends the submitter's
#                      display name to uploads ("ex1 - Shachar.md"), so Drive names are
#                      unstable.
FORM_SOURCES: dict[str, dict] = {
    # The 2026 pilot form: one assignment, no name field, no dropdown. Kept as-is so the
    # existing submissions stay reachable.
    "linear-algebra/hw1": {
        "sheet_id":    "1iAHIzU_Wa7jA_Vagz-7ETLN4tcsUDhj8XSUZ4MynsIk",
        "tab":         None,
        "id_column":   "ID",
        "name_column": None,
        "files":       {"Transcription": "hw1.md"},
    },

    # The course form: ONE form for the whole semester, the "מטלה" dropdown picks the
    # assignment. Adding hw7/hw9/hw10 later is a copy of this entry with a different
    # assignment_value and filename — no new form, sheet, or sharing step.
    #
    # Column names below are the sheet's headers verbatim (read from the live sheet, not
    # typed) — the code matches them literally, and a wrong one reads as "never submitted".
    "linear-algebra/hw3": {
        # University-account form (2026-08-12). Replaced a personal-account form; the column
        # headers are identical, so only the sheet id changed. Submissions made through the
        # old form are NOT reachable from here — they live under the previous sheet.
        "sheet_id":          "1zbukgpJtSxbW6IvhHZJ8TcldOktF_QgdSL6eDAhZeJs",
        "tab":               None,
        "id_column":         "תעודת זהות",
        "name_column":       "שם מלא",
        "assignment_column": "מטלה",
        "assignment_value":  "תרגיל 3",
        "files":             {"קובץ .md של העבודה": "hw3.md"},
    },
}

# ── Student identity ─────────────────────────────────────────────────────────
# A course-neutral key for a student (MULTI_COURSE_MIGRATION §4.3c). GitHub courses
# identify a student by github_username; a Forms course has no GitHub account at all
# and identifies them by their 9-digit university ID.
#
# Both live in ONE column, namespaced, so the two modes cannot collide and the mode is
# visible in the data rather than implied:
#
#     gh:someuser        GitHub Classroom
#     id:318277381       Google Form (university ID)
#
# Derived from FORM_SOURCES, so configuring a Form assignment sets its identity mode
# too — there is no second switch to forget.
IDENTITY_GITHUB = "github_username"
IDENTITY_UNIVERSITY_ID = "university_id"


def identity_mode_for(assignment_name: str) -> str:
    return IDENTITY_UNIVERSITY_ID if assignment_name in FORM_SOURCES else IDENTITY_GITHUB


def student_key_for(assignment_name: str, raw_identifier: str) -> str:
    """Namespaced key for this student on this assignment. Idempotent: a value that is
    already prefixed is returned unchanged, so it is safe to call twice."""
    raw = (raw_identifier or "").strip()
    if raw.startswith(("gh:", "id:")):
        return raw
    if identity_mode_for(assignment_name) == IDENTITY_UNIVERSITY_ID:
        digits = "".join(c for c in raw if c.isdigit())
        return f"id:{digits}" if digits else ""
    return f"gh:{raw}" if raw else ""


def raw_identifier_from(student_key: str) -> str:
    """Strip the namespace — what the adapters and GCS paths actually use."""
    k = (student_key or "").strip()
    return k[3:] if k.startswith(("gh:", "id:")) else k


# ── File paths ───────────────────────────────────────────────────────────────
# ── Course-scoped prompts (MULTI_COURSE_MIGRATION §4.1) ──────────────────────
# COURSE_ID unset  -> backend/prompts/ exactly as before. Byte-identical behaviour;
#                     this is what Operating Systems runs on, and it does not move
#                     until the variable is deliberately set.
# COURSE_ID set    -> courses/<COURSE_ID>/rendered/, the reviewed per-course prompts.
#
# Deliberately NOT a silent switch: the OS rendered prompts differ from the live ones
# by ~130 lines (fileLine, excellent_answer, skeleton-as-input, the removed
# missing-file question), so flipping OS over is a behavioural change to a running
# course and belongs in the off-season.
COURSE_ID = os.environ.get("COURSE_ID", "").strip()

# ── Course scoping of the assignment registry ────────────────────────────────
# With COURSE_ID set, the registry is narrowed to that course's assignments, so a
# Linear Algebra deployment offers only its own homework on the confirm screen and
# never auto-routes a student to an Operating Systems assignment. With COURSE_ID
# unset nothing below changes — OS keeps the hand-maintained lists in the assignment section.
# The prompt folder and the assignment namespace are NOT always the same string: a
# throwaway profile lives in courses/linear-algebra-TEST/ so it is recognisable at a
# glance, while its assignments stay namespaced "linear-algebra/hw1" so the pool files
# don't have to move when the real profile lands. Strip the marker suffix to get the
# namespace, or set COURSE_ASSIGNMENT_NS explicitly when the two genuinely differ.
COURSE_ASSIGNMENT_NS = (os.environ.get("COURSE_ASSIGNMENT_NS", "").strip()
                        or COURSE_ID.removesuffix("-TEST"))

if COURSE_ID:
    _course_assignments = sorted(
        a for a in FORM_SOURCES if a.startswith(f"{COURSE_ASSIGNMENT_NS}/"))
    if not _course_assignments:
        # Never fall through to the OS registry. Silently keeping it is the one
        # outcome this block exists to prevent: the service would serve OS
        # assignments under this course's prompts, and the only visible symptom
        # would be an OS assignment on the confirm screen.
        raise RuntimeError(
            f"COURSE_ID={COURSE_ID!r} matched no assignments: no FORM_SOURCES key "
            f"starts with {COURSE_ASSIGNMENT_NS + '/'!r}. Known keys: "
            f"{sorted(FORM_SOURCES) or '(none)'}. Register the course's assignments "
            f"in FORM_SOURCES, or set COURSE_ASSIGNMENT_NS to their namespace.")
    KNOWN_ASSIGNMENTS = _course_assignments
    DEFAULT_ASSIGNMENT = _course_assignments[0]
    LATEST_ASSIGNMENT = _course_assignments[-1]


# ── Course UI strings (served by /api/config) ────────────────────────────────
# A property of the course, not of the deployment: as env vars these would be one more
# thing to set correctly on every deploy, and getting them wrong shows a maths student
# "is this your code?" — wrong in a way nobody notices until a student says so.
# Keyed by COURSE_ID first, then by the assignment namespace, so a -TEST profile inherits
# its real course's entry without needing a duplicate.
COURSE_UI: dict[str, dict[str, str]] = {
    "": {   # legacy / Operating Systems — COURSE_ID unset
        "title_he":        "מערכות הפעלה — הערכת ידע ומיומנות בתרגילים",
        "submission_kind": "code",
    },
    "linear-algebra": {
        "title_he":        "אלגברה לינארית — הערכת ידע ומיומנות בתרגילים",
        "submission_kind": "solution",
    },
}


def course_ui() -> dict[str, str]:
    """UI strings for this deployment's course.

    Falls back to the legacy entry rather than raising: a missing entry should render
    imperfect wording, not take the service down. A -TEST profile is marked in the title so
    a test deployment is obvious on screen.
    """
    ui = dict(COURSE_UI.get(COURSE_ID)
              or COURSE_UI.get(COURSE_ASSIGNMENT_NS)
              or COURSE_UI[""])
    if COURSE_ID.endswith("-TEST"):
        ui["title_he"] = f"[TEST] {ui['title_he']}"
    return ui


def _rendered_dir(course_id: str) -> str:
    """courses/<course>/rendered — inside the image it sits next to the backend;
    in a source checkout it is one level up. Try both."""
    for base in (_BACKEND_DIR, os.path.dirname(_BACKEND_DIR)):
        cand = os.path.join(base, "courses", course_id, "rendered")
        if os.path.isdir(cand):
            return cand
    # Report the in-image location on failure — the likeliest real-world break is
    # courses/ missing from the Docker context.
    return os.path.join(_BACKEND_DIR, "courses", course_id, "rendered")


def _prompt_path(rendered_name: str, legacy_name: str) -> str:
    if COURSE_ID:
        return os.path.join(_rendered_dir(COURSE_ID), rendered_name)
    return os.path.join(_PROMPTS_DIR, legacy_name)


# ── Per-assignment concept scope ─────────────────────────────────────────────
# courses/<course>/assignment_scope.json maps an assignment to the concepts students
# had been taught by the time it was set.
#
# COURSE_PROFILE.md's DOMAIN_CONCEPTS is the whole semester; this narrows it to one
# assignment, so a question generated for an early assignment cannot reach into material
# the students meet later. Stated as what IS in scope rather than what is excluded — a
# positive list is followed more reliably than a prohibition, and anything absent is
# simply not in scope.
#
# Entirely optional: a course with no file, or an assignment with no entry, gets None and
# every consumer falls back to the full course concept list. So this changes nothing for
# Operating Systems.
_scope_cache: dict[str, dict] = {}


def _scope_file(course_id: str) -> str:
    for base in (_BACKEND_DIR, os.path.dirname(_BACKEND_DIR)):
        cand = os.path.join(base, "courses", course_id, "assignment_scope.json")
        if os.path.isfile(cand):
            return cand
    return ""


def assignment_scope(assignment_name: str) -> "str | None":
    """Concepts in scope for this assignment, or None if unspecified.

    None means "no narrowing" — callers keep the full course concept list rather than
    inventing a boundary. Never raises: a malformed file must not stop an exam, so it is
    reported once and treated as absent.
    """
    if not COURSE_ID:
        return None
    if COURSE_ID not in _scope_cache:
        path = _scope_file(COURSE_ID)
        data: dict = {}
        if path:
            try:
                import json as _json
                with open(path, encoding="utf-8") as fh:
                    data = _json.load(fh)
            except Exception as exc:  # noqa: BLE001
                print(f"[scope] could not read {path}: {exc} — falling back to the "
                      f"full course concept list")
        _scope_cache[COURSE_ID] = data
    value = _scope_cache[COURSE_ID].get(assignment_name)
    return value.strip() if isinstance(value, str) and value.strip() else None


# NB the reviewer prompt is named differently in the two locations:
# backend/prompts/code_reviewer_prompt.txt  vs  rendered/submission_reviewer_prompt.txt
EXAMINER_PROMPT_PATH      = _prompt_path("examiner_prompt.txt", "examiner_prompt.txt")
GRADER_PROMPT_PATH        = _prompt_path("grader_prompt.txt", "grader_prompt.txt")
CODE_REVIEWER_PROMPT_PATH = _prompt_path("submission_reviewer_prompt.txt", "code_reviewer_prompt.txt")
# Second code-review validator (hallucination guard). Loaded lazily, only when
# REVIEWER_VALIDATOR_ENABLED is set (MULTI_COURSE_MIGRATION §4.9). Not part of the live
# grading path until then.
REVIEWER_VALIDATOR_PROMPT_PATH = _prompt_path("reviewer_validator_prompt.txt", "reviewer_validator_prompt.txt")

# GCS path (within GCS_SUBMISSIONS_BUCKET) for the offline question-pool item-analysis report.
# scripts/item_analysis.py --write-gcs writes it; the admin item-analysis panel reads it.
ITEM_ANALYSIS_GCS_PATH = "item_analysis/{assignment}.json"
ASSIGNMENT_README_PATH    = os.path.join(_ASSIGN_DIR, f"{ASSIGNMENT_NAME}_readme.md")
# NOTE: question pools are resolved per-assignment at request time in main.py
# (`{assignment}_question_pool.json`), not from a module-level constant.

# ── Models ───────────────────────────────────────────────────────────────────
EXAMINER_MODEL            = "claude-opus-5"
GRADER_MODEL              = "claude-opus-5"
CODE_REVIEWER_MODEL       = "claude-opus-5"
ANTHROPIC_FALLBACK_MODEL  = "claude-sonnet-5"
GEMINI_FALLBACK_MODEL     = "gemini-2.5-pro"   # requires GEMINI_API_KEY + google-generativeai

# Debug flags — flip these for cheaper/faster testing runs
FORCE_SONNET          = False   # use claude-sonnet-5 for all Anthropic calls
FORCE_GEMINI_FALLBACK = False   # skip Anthropic entirely, route to Gemini

# ── GitHub ────────────────────────────────────────────────────────────────────
# GITHUB_ORG: the GitHub org that owns all student repos.
# GITHUB_REPO_PATTERN: Python format string for the repo name.
#   {assignment_name} → ASSIGNMENT_NAME above
#   {github_username} → student's GitHub login supplied at fetch time
#   Default matches the GitHub Classroom naming convention: "{assignment}-{username}"
# GITHUB_BRANCH: branch to read files from.
# GITHUB_FILES_PATH: sub-folder inside the repo where the .c files live ("" = root).

GITHUB_ORG          = os.environ.get("GITHUB_ORG", "")
GITHUB_REPO_PATTERN = os.environ.get("GITHUB_REPO_PATTERN", "{assignment_name}-{github_username}")
GITHUB_BRANCH       = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_FILES_PATH   = os.environ.get("GITHUB_FILES_PATH", "")  # e.g. "src/" or ""
