# Automated Oral Exam — Technical Specification

> **Purpose of this document.** A developer (human or a fresh Claude Code session) should be able to read this end-to-end and understand the system well enough to add a feature correctly without re-deriving the architecture. It reflects the code as it actually is, not how older docs describe it. Where the legacy docs (`PROJECT_CONTEXT.md`, `SYSTEM_CAPABILITIES.md`) disagree with the code, the code wins — see [§13 Legacy doc corrections](#13-legacy-doc-corrections).

---

## 1. System overview

The system runs **AI-driven oral exams** for the Bar-Ilan University Operating Systems course. A student submits code to GitHub Classroom, then sits a ~15-minute, 3-question adaptive oral exam in which an LLM "Examiner" interrogates them about *their own* submitted code. The goals are to (a) verify the student actually authored and understands their submission, (b) measure depth of understanding, and (c) produce a defensible final grade with a human-readable report for staff.

It is a **stateless FastAPI backend** plus a **Next.js backend-for-frontend (BFF)**. All per-exam state lives in a Cloud SQL Postgres database; the API holds nothing in process memory between requests except read-only lookup maps loaded at startup. Grading runs **asynchronously** after the exam ends, as a chain of three LLM agents.

### 1.1 High-level architecture

```
┌──────────────┐      HTTPS       ┌─────────────────────────┐
│   Student    │ ───────────────▶ │  Next.js frontend (BFF) │  Cloud Run, public
│   browser    │ ◀─────────────── │  exam-frontend-ex1      │  (allow-unauthenticated)
└──────────────┘                  │  - React UI (App Router)│
                                  │  - /api/* proxy routes  │
                                  └───────────┬─────────────┘
                                              │ mints Google ID token
                                              │ (Cloud Run IAM)
                                              ▼
                                  ┌─────────────────────────┐
                                  │  FastAPI backend         │  Cloud Run, PRIVATE
                                  │  ai-exam-backend-ex1     │  (IAM-authenticated only)
                                  │  - stateless endpoints   │
                                  │  - LLM agent calls       │
                                  │  - async grading task    │
                                  └──┬───────┬───────┬───────┘
                                     │       │       │
              ┌──────────────────────┘       │       └────────────────────┐
              ▼                               ▼                            ▼
   ┌────────────────────┐        ┌──────────────────────┐     ┌──────────────────────┐
   │ Cloud SQL Postgres │        │ Anthropic / Gemini   │     │ Google Cloud Storage │
   │ users, sessions    │        │ Examiner/Grader/     │     │ submissions, results │
   │ (all exam state)   │        │ Code-Reviewer agents │     │ rosters, ID maps     │
   └────────────────────┘        └──────────────────────┘     └──────────────────────┘
              │                                                          ▲
              ▼                                                          │
   ┌────────────────────┐   ┌──────────────────────┐   ┌────────────────────────────┐
   │ GitHub App (repos) │   │ Google Sheets (survey)│  │ Google Calendar (slots)     │
   │ student code fetch │   │ Gmail SMTP (emails)   │  │ admin cross-referencing     │
   └────────────────────┘   └──────────────────────┘   └────────────────────────────┘
```

### 1.2 Request lifecycle in one sentence

The frontend proxy receives a student action, mints a Google ID token, forwards it to the private backend; the backend loads the session row from Postgres, reconstructs the in-flight exam state (question picker + examiner message history), calls the Examiner LLM, persists the new state back to Postgres, and returns the next question — holding **no state in memory** between calls.

---

## 2. Repository layout

```
Automated Oral Exam/
├── backend/                      # FastAPI app (source of truth)
│   ├── main.py                   # ~3,500 lines — all endpoints, grading pipeline, admin
│   ├── agents.py                 # LLM agent schemas + call_agent cascade
│   ├── plan_assembler.py         # QuestionPicker (adaptive question selection)
│   ├── config.py                 # assignment names, file lists, model IDs, paths
│   ├── models.py                 # SQLAlchemy ORM: User, Session, ResultSummary
│   ├── result_summary.py         # the single funnel keeping ResultSummary in sync (§4.4)
│   ├── schemas.py                # Pydantic request/response models
│   ├── database.py               # Cloud SQL Connector + SQLAlchemy engine (lazy connector)
│   ├── github_stub.py            # GitHub App auth + submission fetch → GCS
│   ├── forms_stub.py             # Google Forms/Drive intake → GCS (same layout)
│   ├── submission_source.py      # routes intake per assignment: GitHub | Forms
│   ├── google_apis.py            # Google Sheets (surveys) + Calendar
│   ├── roster_utils.py           # Classroom roster CSV loader
│   ├── accommodations.py         # extended-time student lookup
│   ├── grade_email_template.py   # student grade email (Hebrew, RTL HTML)
│   ├── distress_email_template.py# TA distress notification template
│   ├── prompts/                  # examiner/grader/code_reviewer + reviewer_validator (flag-gated)
│   ├── assignments/              # per-assignment README + question pool JSON + man pages
│   ├── scripts/                  # backfills+migrations+probes; item_analysis.py, backfill_result_summary.py
│   ├── tests/                    # pytest: distress, timeout metadata
│   ├── Dockerfile                # python:3.11-slim, uvicorn on :8080
│   └── requirements.txt
├── frontend/exam-frontend/       # Next.js App Router (TypeScript)
│   ├── src/app/                  # pages + /api proxy routes
│   ├── src/components/           # React UI components
│   ├── src/hooks/useExamState.ts # client exam state machine
│   ├── src/lib/backend-proxy.ts  # BFF proxy w/ Google ID-token minting
│   ├── src/middleware.ts         # admin/QA route gating
│   └── Dockerfile
├── question_pool_creation/       # tooling to author + audit question pools
├── private-data/                 # student PII (gitignored): ID maps, group lists, emails
├── cloudbuild*.yaml              # Cloud Build pipelines (backend + frontend variants)
├── *.ps1                         # local dev + ops helper scripts (Windows)
├── archive/                      # ⚠️ superseded snapshots, kept for history only:
│                                 #   PROJECT_CONTEXT.md (partly outdated — see §13),
│                                 #   SYSTEM_CAPABILITIES.md (mostly accurate),
│                                 #   TODO_admin.md, admin-commands.md, sites.MD,
│                                 #   oral-exam-frontend-architecture.md
└── docs/                         # ← this document + SYSTEM_QUALITIES.md (current)
```

---

## 3. Modules and what they do

### Backend

| Module | Responsibility |
|---|---|
| `main.py` | The whole HTTP surface: auth/start, answer, timeout, complaint, lookup, preview, admin viewers, cron email jobs, regrade. Also the async grading pipeline `run_grader_background()` and all in-memory ID/roster maps loaded at startup. |
| `agents.py` | Pydantic output schemas for the agents (`ExaminerOutput`, `CodeReviewerOutput`, `GraderOutput`, and `ReviewerValidatorOutput` — the §4.9 hallucination guard); `call_agent()` (the provider cascade with tool-forcing + prompt caching); the per-agent wrappers `call_examiner_q1`, `call_examiner_qn`, `call_code_reviewer`, `call_reviewer_validator`, `call_grader`; and `compute_final_grade()`. |
| `plan_assembler.py` | `QuestionPicker` — stateful, per-session adaptive question selection over the assignment's question pool. Serializes to/from a dict for DB storage (`to_state`/`from_state`). |
| `config.py` | Assignment registry: `ASSIGNMENT_NAME`, `ASSIGNMENT_FILES`, repo patterns, labels, known/QA assignment sets, model IDs, prompt paths (incl. `REVIEWER_VALIDATOR_PROMPT_PATH`), debug flags, GitHub env defaults. **Edit `ASSIGNMENT_NAME` when switching the active assignment.** |
| `models.py` | ORM tables: `User`, `Session` (entire serialized exam state), and `ResultSummary` (derived read-model for the admin dashboard — see "Admin aggregation" below). |
| `result_summary.py` | The single funnel that keeps `ResultSummary` in sync: `summary_from_blob()` (pure transform) + `upsert_summary()`. Every grade-write path must call `upsert_summary_from_blob()`. Derived model — GCS blobs remain source of truth. |
| `schemas.py` | Pydantic request/response DTOs for every endpoint. |
| `database.py` | `get_db()` FastAPI dependency; SQLAlchemy engine over Cloud SQL Connector + pg8000. Connector is built lazily (first query, not import) so the module is importable offline. |
| `github_stub.py` | GitHub App JWT→installation-token auth; resolves the student repo (with re-accept variant probing); fetches files → saves to GCS; builds the exam code context. |
| `forms_stub.py` | The non-GitHub intake. Reads a Google Form's linked responses sheet, extracts the Drive file id per upload, downloads it, and writes to the **same** GCS layout `{assignment}/{student_key}/{filename}`. Configured per assignment in `config.FORM_SOURCES`. Needs `drive.readonly` in `google_apis._SCOPES` and the Drive API enabled. |
| `submission_source.py` | Routes intake per assignment — `google_form` if the assignment is in `FORM_SOURCES`, else `github`. Exposes the same names `main.py` used to import from `github_stub`, so both mechanisms run side by side in one deployment. Also `fetch_id_file()`: reads `id.txt` on the GitHub path, and returns the 9-digit form field on the Forms path (there is no `id.txt` in a Form submission). |
| `google_apis.py` | Reads pre/post survey responses from Google Sheets; reads exam-slot registrations from Google Calendar; helpers to bucket events by day/hour for admin stats. |
| `roster_utils.py` | Loads GitHub Classroom roster CSV (`github_username → name + email`) from GCS or local. |
| `accommodations.py` | Loads the extended-time student ID list; `is_extended_time()` decides the per-session exam duration. |
| `grade_email_template.py` | Builds the Hebrew student grade email (plain + RTL-HTML), including the `ADAPTATION_BONUS_POINTS` bonus and post-survey link. |
| `distress_email_template.py` | Subject/body template for the TA distress notification. |

### Frontend (`frontend/exam-frontend`)

| Area | Responsibility |
|---|---|
| `src/app/page.tsx`, `exam/page.tsx`, `qa/*`, `admin/*` | Pages. Student entry/exam flow; QA flow; admin dashboards (assignment view, per-student view). |
| `src/app/api/**/route.ts` | Thin proxy routes. Each one validates input and forwards to the matching backend endpoint via `proxyToBackend()`. They never talk to the DB or LLMs directly. |
| `src/hooks/useExamState.ts` | The client-side exam state machine (phases, timer, transcript, file navigation). Drives the whole student UX. |
| `src/lib/backend-proxy.ts` | Mints a Google ID token for the backend's Cloud Run URL (or skips auth for localhost) and forwards the request. The single chokepoint for backend access. |
| `src/lib/types.ts`, `uiStrings.ts`, `welcomeStrings.ts` | Shared TS types; bilingual UI strings. |
| `src/middleware.ts` | Gates `/admin` and `/api/admin` behind `ADMIN_ENABLED`; gates `/exam` to the QA flow when `NEXT_PUBLIC_QA_MODE`. |
| `src/components/*` | Entry, roster/assignment confirm, preferences, code panel/viewer, file tabs, question display, answer input, timer, completed/distress screens, "not my code" + report-problem modals. |

---

## 4. Data models

### 4.1 Database (`models.py`) — Cloud SQL Postgres

**`User`**
- `github_username` (PK, string)

**`Session`** — one row per exam attempt; holds the *entire* serialized exam state.

| Column | Type | Meaning |
|---|---|---|
| `session_id` | UUID string (PK) | session identifier |
| `github_username` | FK → User | the examinee |
| `start_time` | datetime | exam start |
| `status` | string | lifecycle: `in-progress` → `completed` → `graded`; also `invalidated`, `complaint_pending`, `ended_distress` |
| `transcript` | Text (JSON) | full Q&A + examiner internal JSON per turn |
| `examiner_messages` | Text (JSON) | Anthropic message history (for stateless reconstruction) |
| `picker_state` | Text (JSON) | serialized `QuestionPicker` state |
| `pending_tool_use_id` | string | open tool-use id for the forced-tool call continuity |
| `turn` | int | current turn index |
| `session_seed` | BigInteger | RNG seed for deterministic question picking |
| `examiner_temp` | Float | per-session examiner temperature |
| `student_files_context` | Text | the code context string shown to the examiner |
| `assignment_name` | string | which assignment this attempt is for |
| `persona` | string | requested persona (UX/voice) |
| `language` | string (default `he`) | `he` or `en` |
| `github_username_manual` | bool | username was typed manually vs. roster-confirmed |
| `timed_out` | bool | whether the exam hit the time limit |
| `timeout_metadata` | Text (JSON) | details captured at timeout |
| `switch_used` | bool | student already used their one allowed topic switch |
| `reask_pending` | bool | a RE_ASK is in flight for the current question |
| `student_id` | string | 5-digit ID parsed from `id.txt` |
| `full_id_from_repo` | string | 9-digit ID parsed from `id.txt` |
| `id_resolution_status` / `id_resolution_detail` | string | how the student name/ID was resolved |
| `student_key` | string | course-neutral identity: `gh:<username>` or `id:<9 digits>`, derived by `config.student_key_for()`. Written on every new session; **nothing reads it yet** — `github_username` remains authoritative. See MULTI_COURSE_MIGRATION §4.3c. |
| `final_grade` | Text (JSON) | `{oralDefenseScore, staticCodeQualityScore, finalWeightedGrade}` |
| `professor_report` | Text | staff-facing report (Hebrew) |
| `code_review` | Text (JSON) | Code Reviewer agent output |
| `grader_verdict` | Text (JSON) | Grader agent output |
| `grade_email_sent` | bool (nullable) | whether the grade email has been dispatched |

**`ResultSummary`** — derived read-model for the admin dashboard (added 2026-07; see §4.4).
One row per `(assignment_name, github_username)` (composite PK), holding only the ~15 fields
the dashboard aggregates: `student_id`, `full_id`, `hebrew_name`, `id_resolution_status`,
`final_grade`/`oral_score`/`static_score` (ints), `authorship`, `integrity_flag`,
`prompt_injection_flag`, `reviewer_challenged`, `status`, `timed_out`, `switch_used`,
`duration_min`, `exam_date`, `updated_at`. **Not the source of truth** — the GCS result blob
is; this table is a rebuildable projection. Auto-created by `create_all` on startup.

### 4.2 LLM agent schemas (`agents.py`)

These Pydantic models are converted to Anthropic **tool schemas** and the model is *forced* to call the tool, so output is always valid structured JSON.

- **`ExaminerOutput`**: `internalReasoning`, `questionNumber`, `questionText` (Hebrew, shown to student), `action` ∈ `{JUMP_TO_LINE, NONE, RE_ASK, FINISH_EXAM, END_EXAM_DISTRESS}`, `actionParameters` (fileName, codeLine), `internalEvaluation` (`understandingScore` 1–5, `authorshipConfidence` high/medium/low, `integrityFlag`, `suspectedPromptInjection`, `notes`), `bugPivotUsed`, `switchGranted`, `chosenTopicLabel`, `chosenTopicDifficulty`, `nextQuestionDifficulty`, `studentPersona`.
- **`CodeReviewerOutput`**: `staticCodeQualityScore` (0–100), `studentStaticFeedback` (Hebrew, shown to student), `codeReviewNotes` (English, staff), `signalBAssessment` (`markersFound`, `level` none/low/moderate/high, `analysis`) — the LLM-authorship style signal.
- **`GraderOutput`**: `grading_scratchpad`, `authorshipAssessment` (established/partial/not_established), `integrityFlag`, `promptInjectionFlag`, `academicDishonestyReasoning`, `oralDefenseScore` (0–100), `studentFeedback` (Hebrew, shown to student), `professorReport` (Hebrew, staff).
- **`ReviewerValidatorOutput`** (2026-07): the §4.9 hallucination guard — `challenges[]` (each: `deduction`, `category`, `evidence`, `confidence`), `any_unfair_deductions`, `corrected_static_score` (≥ original), `corrected_student_feedback` (minimally edited), `summary`. Audits the code reviewer's deductions for over-penalization only, then **restores wrongly-removed points and fixes the feedback — it can only raise the score, never lower it**. Runs only when `REVIEWER_VALIDATOR_ENABLED` is set, gated on score<100. See `MULTI_COURSE_MIGRATION.md` §4.9.

### 4.3 Question pool (`assignments/{name}_question_pool.json`)

A list of question objects, each: `id`, `focus` (uniqueness key), `dimension` (design_choice / edge_case / error_handling / api_depth / code_flow / cross_file), `difficulty` (easy/medium/hard), `files` (which submitted files it targets), `conflicts_with` (ids that must not co-occur in one exam), `examiner_notes` (a menu of probe ideas for the examiner). Pools generated by the next-year pipeline additionally carry `excellent_answer` (a grader-only scoring anchor — see `MULTI_COURSE_MIGRATION.md` §4.7b).

### 4.4 Admin aggregation — two paths

The admin dashboard aggregate can be served two ways:

1. **`/results/aggregate` (blob-backed, original).** `_load_assignment_blobs()` downloads
   *every* result blob from GCS (~35 MB for a-3) and aggregates in Python. Correct but slow
   and memory-heavy (this is why the backend is 3Gi and strips `examiner_messages`).
2. **`/results/aggregate_fast` (table-backed, 2026-07).** Reads the `ResultSummary` table
   (~550 tiny rows) and aggregates identically. Sub-50 ms, ~0 memory.

`ResultSummary` is kept in sync by **one funnel**, `result_summary.upsert_summary_from_blob()`,
which must be called by every path that writes a grade (grading, regrade, appeal edits). Today
`run_grader_background` calls it behind `RESULT_SUMMARY_ENABLED` (off by default). Rebuild the
whole table any time from the blobs (the truth) with `scripts/backfill_result_summary.py`.
Full rationale + enable steps: `MULTI_COURSE_MIGRATION.md` §4.10.

### 4.5 Offline pool item-analysis

`scripts/item_analysis.py` scores each pool question from the graded blobs — take rate,
routing-corrected residual difficulty, discrimination, scoring ceiling, and **semantic
divergence** (mean pairwise cosine of the question's instantiation embeddings; needs the
optional `sentence-transformers` dep) — and prints recommendations. Offline, run after an
assignment closes. `MULTI_COURSE_MIGRATION.md` §4.8.

---

## 5. API endpoints (backend)

All under the FastAPI app in `main.py`. The frontend reaches these only through its `/api/*` proxy routes.

### Student-facing
- `POST /api/auth/start` — Begin an exam. One-time-use lock per username; fetches submission from GitHub; builds code context; picks Q1 (medium); calls Examiner for the first question; computes per-student duration (default **960s**, extended-time students **1140s**). Returns `StartResponse` (session_id, first question, files map, duration).
- `POST /api/exam/answer` — Submit an answer. Reconstructs picker + examiner messages from the DB row, peeks 6 candidate questions (2× easy/medium/hard), calls the Examiner, handles `FINISH_EXAM` / `END_EXAM_DISTRESS` / `RE_ASK` / switch, registers the chosen topic, persists, returns the next question or finish. On finish, schedules `run_grader_background`.
- `POST /api/exam/timeout` — Student ran out of time; records `timeout_metadata`, marks `timed_out`, ends and schedules grading.
- `POST /api/exam/complaint` — "Not my code" / problem report. Locks the username (`complaint_pending`) and emails staff. Distress events also notify the TA.
- `GET /api/exam/lookup/{github_username}` — Pre-exam check: does a submission exist, which assignment, is the username already used/locked, what assignments are available. Drives the entry → assignment-confirm flow.
- `POST /api/exam/preview` — Returns the student's fetched files (for the confirm/roster UI).

### Admin (guarded by `_require_admin`, header `X-Admin-Key` == `VIEWER_PASSWORD`)
- `POST /api/admin/fetch-submission` — Manually pull a student's repo into GCS.
- `POST /api/admin/invalidate-session` and `POST /api/admin/invalidate/{github_username}` — Invalidate session(s) so a student can retake.
- `POST /api/admin/reload-id-map`, `POST /api/admin/reload-username-fallback-map` — Hot-reload the in-memory PII maps without redeploying.
- `GET /api/admin/results/assignments`, `/results/by-github/{username}`, `/results/email-status`, `/results/aggregate` (histogram/outliers/flagged — downloads every blob), `/results/aggregate_fast` (**same shape, reads the `ResultSummary` table instead of blobs — see §4.4**; returns `{"empty_table": true}` if not backfilled), `/results/export.csv`, `/results/{github_username}` (**wildcard — must stay the last route registered**).
- `GET /api/admin/stats/{assignment}` — Big cross-reference: Calendar slots vs. actual sessions (ghost_slots, wrong_time_slots, mismatches, no_slot), session timing, per-student survey/calendar matching.
- `GET /api/admin/assignment/{assignment}/question-stats` — Aggregate question usage/difficulty stats.
- `GET /api/admin/student-sessions/{username}` — All sessions for a student.
- `GET /api/admin/.../reminder-preview`, `send-reminder-emails`, `send-test-grade-email`, `send-test-reminder-email`.
- `POST /api/admin/regrade/{session_id}` — Synchronous re-run of the grading pipeline.

### Cron (called by Cloud Scheduler)
- `POST /api/cron/send-grade-emails` — Daily; sends grade emails for newly graded sessions (midnight-Israel cutoff).
- `POST /api/cron/send-reminder-emails` — Day-before exam reminders (Asia/Jerusalem).

### Health
- `GET /health`.

**Routing caveat:** the wildcard `GET /api/admin/results/{github_username}` must remain registered *after* all the more specific `/api/admin/results/*` routes, or it will shadow them.

---

## 6. Key workflows (step by step)

### 6.1 Taking an exam

1. **Entry.** Student types GitHub username → frontend calls `GET /api/exam/lookup/{username}`. Backend checks GCS/GitHub for a submission, resolves the assignment, and checks the one-time-use lock. The UI advances through assignment-confirm → roster-confirm → preferences (gender/language) → briefing.
2. **Start.** Frontend `POST /api/exam/start`. Backend: sets the one-time lock; fetches the repo via the GitHub App (`github_stub.fetch_and_save_submission`) into GCS if not already there; builds the code context (missing files marked `[NOT SUBMITTED]`); seeds a `QuestionPicker`; picks two medium Q1 options; calls `call_examiner_q1`; determines duration (id.txt / roster → extended-time check); writes the Session row; returns the first question + files map + `exam_duration_seconds`.
3. **Answer loop (×3 questions).** For each answer, `POST /api/exam/answer`: load Session, rebuild `QuestionPicker` (`from_state`) and the examiner message list, `peek_options(["easy","easy","medium","medium","hard","hard"])`, call `call_examiner_qn`. The Examiner picks a label + difficulty (IRT: step up if score ≥4, down if ≤2.5, else stay), may `JUMP_TO_LINE`, `RE_ASK` (once per question), grant one `switch`, pivot to a bug, or `FINISH_EXAM`/`END_EXAM_DISTRESS`. The chosen topic is registered (`mark_used`) and all state is persisted back.
4. **Finish.** When the Examiner returns `FINISH_EXAM` (or the student times out / triggers distress), the session is marked ended and `run_grader_background(session_id)` is scheduled as a FastAPI BackgroundTask. The student sees the completed (or compassionate distress) screen.

### 6.2 Grading (async, 3 phases — `run_grader_background`)

1. **Phase 1 — Code Reviewer.** `call_code_reviewer` (temp 0.1) sees the README + the student's source code but is **blind to the transcript**. Produces `staticCodeQualityScore`, student static feedback, and **Signal B** (LLM-authorship style assessment).
   - **Phase 1b — Reviewer Validator** *(optional, `REVIEWER_VALIDATOR_ENABLED`, gated on score<100)*: `call_reviewer_validator` audits the reviewer's deductions for over-penalization. When it finds unfair ones it **restores the wrongly-removed points (only ever raises the score) and minimally edits the student feedback** — the corrected `staticCodeQualityScore` then flows into the final grade. Originals are preserved (`originalStaticCodeQualityScore`, `originalStudentStaticFeedback`) and the full audit rides in the blob (`code_review.reviewerValidation`). MIGRATION §4.9.
2. **Phase 2 — Grader.** `call_grader` (temp 0.1) sees the README + **Signal B** + the **transcript**, but is **blind to the code**. It re-evaluates the Examiner's per-turn scores (it may override them), places the student in a 2D IRT table (avg score × difficulty reached) to get `oralDefenseScore`, and decides `authorshipAssessment` via a Signal-A/Signal-B table. `extra_notes` injected from the transcript flag timeout/switch/RE_ASK events and incomplete exams.
3. **Phase 3 — Mechanical combine + identity.** `compute_final_grade(oral, static) = round(0.75*oral + 0.25*static)` (**no caps, no penalties** — see §13). Then fetch `id.txt` from the repo, parse the student ID, and resolve the real name via a 3-tier chain (id_mapping CSV → secondary username-fallback map → Classroom roster). Persist `final_grade`, `professor_report`, `code_review`, `grader_verdict` to the Session row and write a GCS result blob at `results/{assignment}/{username}.json`. If `RESULT_SUMMARY_ENABLED`, also upsert the `ResultSummary` row (§4.4).

> The **student-facing final grade** shown in the email adds `ADAPTATION_BONUS_POINTS` (currently **+10**, capped at 100) on top of `finalWeightedGrade`. That bonus lives only in `grade_email_template.py`, not in the stored `final_grade`.

### 6.3 Grade email dispatch
`POST /api/cron/send-grade-emails` (daily) finds graded, un-emailed sessions, validates the blob has all required fields (`validate_email_readiness`), builds the Hebrew RTL email (`build_grade_email` + `build_grade_email_html`), sends via Gmail SMTP, and sets `grade_email_sent`.

---

## 7. External integrations

| Integration | How it's used | Auth |
|---|---|---|
| **Anthropic Claude** | Examiner, Grader, Code Reviewer agents via forced tool-use. Primary model `claude-opus-4-6`. | `ANTHROPIC_API_KEY` |
| **Google Gemini** | Last-resort fallback (`gemini-2.5-pro`) when Anthropic is overloaded. Message history is flattened to a single text prompt. | `GEMINI_API_KEY` |
| **GitHub App** | Fetch each student's submission repo. JWT (RS256, 5-min exp) → installation token. Repo name resolved by pattern; probes `-1..-5` re-accept variants and keeps the most recently pushed. | `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY[_PATH]`, `GITHUB_INSTALLATION_ID`, `GITHUB_ORG`, `GITHUB_REPO_PATTERN`, `GITHUB_BRANCH`, `GITHUB_FILES_PATH` |
| **Cloud SQL Postgres** | All exam state. Accessed via `google.cloud.sql.connector` + pg8000 + SQLAlchemy. | `CLOUD_SQL_INSTANCE`, `DB_USER`, `DB_PASS`, `DB_NAME` |
| **Google Cloud Storage** | Submissions, result blobs (`results/{assignment}/{username}.json`), rosters, ID maps, complaints, distress events. | ADC / service account |
| **Google Sheets** | Pre-exam and post-exam (mandatory AI-policy) survey responses, keyed by normalized student ID. | service account (read-only) |
| **Google Calendar** | Exam-slot sign-ups; admin stats cross-reference registrations against actual sessions. | service account (read-only) |
| **Gmail SMTP** | Grade emails, exam reminders, TA distress/complaint notifications. | `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`, `TA_EMAIL` |

Google credentials resolve in order: `backend/keys/ai-examiner-system-*.json` (local) → `GOOGLE_SERVICE_ACCOUNT_KEY_PATH` → Application Default Credentials (Cloud Run).

---

## 8. Environment variables

### Backend (`backend/.env`, mirrored in `.env.example`)
- **LLM:** `ANTHROPIC_API_KEY` (required), `GEMINI_API_KEY` (optional fallback).
- **GitHub App:** `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY` or `GITHUB_PRIVATE_KEY_PATH`, `GITHUB_INSTALLATION_ID`, `GITHUB_ORG`, `GITHUB_REPO_PATTERN` (default `{assignment_name}-{github_username}`), `GITHUB_BRANCH` (default `main`), `GITHUB_FILES_PATH`.
- **Database:** `CLOUD_SQL_INSTANCE`, `DB_USER`, `DB_PASS`, `DB_NAME`.
- **Storage / maps:** `GCS_SUBMISSIONS_BUCKET`, `ID_MAPPING_GCS_PATH`, `GOOGLE_SERVICE_ACCOUNT_KEY_PATH`.
- **Email:** `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`, `TA_EMAIL`.
- **Admin:** `VIEWER_PASSWORD` (checked against the `X-Admin-Key` header).
- **Exam config:** `ASSIGNMENT_NAME` (overrides `config.py`), `EXAM_DURATION_SECONDS` (default 960).
- **Course scoping:** `COURSE_ID` — **unset means legacy**: prompts load from `backend/prompts/`
  and the assignment registry is the hand-maintained list in `config.py`. That is what Operating
  Systems runs on. When set (e.g. `linear-algebra`), prompts load from
  `courses/<COURSE_ID>/rendered/` and `KNOWN_ASSIGNMENTS`/`DEFAULT_ASSIGNMENT`/`LATEST_ASSIGNMENT`
  are narrowed to that course's entries in `FORM_SOURCES`. It is a **per-deployment** variable —
  one Cloud Run service per course. Startup logs the resolved prompt paths and a content hash of
  each (`[prompts]` lines), and every exam start logs the course, examiner-prompt hash, intake
  source and student key (`[session:start]`).
- **Course scoping, part 2:** `COURSE_ASSIGNMENT_NS` — the namespace the course's `FORM_SOURCES`
  keys are prefixed with. It defaults to `COURSE_ID` minus a trailing `-TEST`, which is what makes
  the throwaway profile in `courses/linear-algebra-TEST/` find assignments named
  `linear-algebra/hw1`. **Set it explicitly whenever the prompt folder name and the assignment
  prefix differ for any other reason** — they are two different things and only coincide by
  convention. If `COURSE_ID` is set and nothing matches, startup now raises rather than quietly
  keeping the OS registry; see §14.1.
- **Feature flags (2026-07, all default OFF — a deploy is inert until set):**
  - `RESULT_SUMMARY_ENABLED` — when `true`, `run_grader_background` upserts the `ResultSummary`
    read-model on every grade (powers `/results/aggregate_fast`). See §4.4 / MIGRATION §4.10.
  - `REVIEWER_VALIDATOR_ENABLED` — when `true`, runs the second code-review validator
    (hallucination guard) after the code reviewer, gated on `staticCodeQualityScore < 100`.
    Corrects over-penalization: restores wrongly-removed points (score can only rise) and
    minimally fixes the feedback; originals kept for audit. See MIGRATION §4.9.

> `.env.example` documents only the LLM + GitHub vars; the DB/GCS/SMTP/admin vars are real and required in production but not listed there. Keep that in mind when standing up a new environment.

### Frontend (Cloud Run env / build args)
- `BACKEND_URL` — the private backend Cloud Run URL the BFF proxies to.
- `GOOGLE_SA_KEY_JSON` — service-account JSON used to mint ID tokens (omit for ADC).
- `ADMIN_ENABLED` — `true` only on the admin deployment; gates `/admin` + `/api/admin` in middleware. **No `NEXT_PUBLIC_` prefix** so it stays a runtime secret, not baked into the JS bundle.
- `NEXT_PUBLIC_QA_MODE` / `QA_MODE` — QA deployment flag.
- `NEXT_PUBLIC_EXAM_DURATION_SECONDS` / `EXAM_DURATION_SECONDS` — default exam length (960).

---

## 9. The LLM agent layer (`agents.py`) in detail

- **`call_agent(...)`** is the single entry point. It builds an Anthropic request with the agent's Pydantic schema as a forced tool (`tool_choice`), `max_tokens=4096`, prompt caching (`cache_control: ephemeral`) on the large static blocks, then **cascades on HTTP 429/529**: `claude-opus-4-6` → `claude-sonnet-4-6` → `gemini-2.5-pro`. For Gemini it flattens the message history into one text prompt and parses JSON out of the response.
- **`call_examiner_q1`** — provides exactly two medium options (`medium-1`, `medium-2`); the examiner picks the more code-relevant one.
- **`call_examiner_qn`** — provides six options (easy/medium/hard ×2), and injects the current switch status and any RE_ASK block into the prompt.
- **`call_code_reviewer`** — temp 0.1; sees code + README, blind to transcript.
- **`call_grader`** — temp 0.1; sees README + Signal B + transcript, blind to code.
- **`compute_final_grade(oral, static)`** → `round(0.75*oral + 0.25*static)`.

Debug flags in `config.py`: `FORCE_SONNET` (route all Anthropic calls to Sonnet) and `FORCE_GEMINI_FALLBACK` (skip Anthropic entirely). Both default `False`.

---

## 10. Adaptive question selection (`plan_assembler.py`)

`QuestionPicker` keeps per-session `used_focuses`, `used_files`, `used_dims`, `excluded_ids`, a `turn` counter, and an RNG seeded by `session_seed` (stored on the Session row for determinism). Scoring in `pick_question`: **+100** exact difficulty match, **+40** adjacent difficulty, **+50** if it touches an unused file, **+25** unused dimension / **−15** used dimension, plus `rng.random()*40` jitter; it then samples from a top tier (within 60 points of the max). `peek_options` returns one candidate per requested difficulty **without mutating state** (so the Examiner can choose among them), and `mark_used`/`_register` commit the choice and expand `excluded_ids` using `conflicts_with` bidirectionally. State round-trips through `to_state`/`from_state` for the stateless API.

---

## 11. Frontend BFF pattern

The backend Cloud Run service is **private** (IAM-only). The browser never holds GCP credentials. Every browser request hits a Next.js `/api/*` route, which calls `proxyToBackend(path, {method, body})` in `src/lib/backend-proxy.ts`. That function:
- For a localhost backend (dev via `gcloud` proxy), forwards without auth.
- For production, calls `GoogleAuth.getIdTokenClient(BACKEND_URL)` to mint a Cloud Run **ID token** and attaches it as the `Authorization` header.

The proxy routes are deliberately thin: validate input, forward, pass through status + JSON. `src/middleware.ts` returns 404 for `/admin` and `/api/admin` unless `ADMIN_ENABLED=true`, and constrains `/exam` to the QA flow in QA deployments. The same Docker image is deployed three ways (student `exam-frontend-ex1`, `exam-admin` with `ADMIN_ENABLED`, and a QA variant) differing only by env vars.

The client state machine `useExamState.ts` owns phases (`entry → roster_lookup → assignment_confirm → roster_confirm → preferences → briefing → loading → active → completed/distress/error`), the countdown timer (wall-clock based, ticks every 500ms, fires `/api/exam/timeout` at zero), the transcript, and `JUMP_TO_LINE`-driven code auto-scroll (`scrollRevision`).

---

## 12. Identity resolution & accommodations

- **`id.txt`** in each repo carries the student's ID. `_parse_id_txt` yields a 5-digit and/or 9-digit ID plus a status (`ok_9_digits`, `ok_5_digits`, `missing_file`, `empty_file`, `no_digits`, `wrong_length`, `fetch_error`).
- **Name resolution chain** (Phase 3 of grading): canonical `id_mapping.csv` (`_by_full_id` / `_by_last5` / `_by_name`) → `github_username_fallback_ids.csv` → Classroom roster (`roster_utils`). Ambiguous 5-digit matches are flagged.
- **Extended time** (`accommodations.py`): IDs in `private/extended_time_ids.txt` (GCS) or local get `EXTENDED_TIME_SECONDS = 1140` (19 min) instead of the default 960 (16 min). Matching is by 9-digit or 5-digit suffix.

---

## 13. Legacy doc corrections (read before trusting old docs)

`PROJECT_CONTEXT.md` and `SYSTEM_CAPABILITIES.md` are **point-in-time snapshots**. Useful for intent, wrong on specifics:

- **Database:** old docs say **SQLite** (`exam.db`). Production is **Cloud SQL Postgres**. (`backend/exam.db` / `test_distress.db` are stale local artifacts.)
- **Grade formula:** old docs describe authorship caps (min 70/80) and an "oral < 50" penalty. The actual `compute_final_grade` is a **plain weighted average with no caps and no penalties**. The only adjustment anywhere is the **+10 adaptation bonus**, applied in the email template, not the stored grade.
- **Models:** old docs list the code reviewer as Sonnet. All three agents use **`claude-opus-4-6`** by default (`config.py`), with Sonnet/Gemini as fallback only.
- **Removed references:** `cli_tester.py` and an `exercises/` directory mentioned in old docs no longer exist.

---

## 14. How to add a feature

**General loop:** change the backend endpoint/logic in `main.py` (+ schema in `schemas.py`, + ORM column in `models.py` if you need to persist something), add or adjust the matching thin proxy route under `frontend/.../src/app/api/...`, then wire the UI in `useExamState.ts` + a component. Keep the backend **stateless** — anything that must survive between requests goes on the `Session` row, not in module globals.

Common cases:

- **Add a new assignment.** In `config.py`: add to `ASSIGNMENT_FILES`, `ASSIGNMENT_LABELS`, `KNOWN_ASSIGNMENTS`, and (if the repo naming differs) `ASSIGNMENT_REPO_PATTERNS`. Add `assignments/{name}_readme.md` and `{name}_question_pool.json` (+ optional `{name}_man_pages.txt`). Set `ASSIGNMENT_NAME` (or the `ASSIGNMENT_NAME` env var) to make it active. Author the pool with the two-step prompts in `question_pool_creation/` (Step 1 generates candidates, Step 2 prunes/rebalances/assigns `conflicts_with`). The pool must pass `validate_no_conflicts` at load.
- **Add a new assignment collected by a Google Form** (not GitHub). Five steps, in order:
  1. **Create the form** — one per assignment. Fields: the 9-digit university ID (short answer,
     response validation regex `^\d{9}$`) and a file upload for the transcription. Turn on
     *Settings → Responses → Collect email addresses → Verified*, or a mistyped ID is
     unrecoverable. Link it to a responses sheet.
  2. **Share the responses sheet _and_ the Drive folder holding the uploads** (Viewer) with
     **`1023741330092-compute@developer.gserviceaccount.com`** — the Cloud Run runtime service
     account. Both are needed: the sheet gives a per-file Drive id, and reading that file needs
     access to the file itself.
     ⚠️ **Not the same identity as local dev.** `google_apis._credentials()` prefers
     `backend/keys/ai-examiner-system-*.json` (→ `ai-examiner-system@…`), but `backend/keys/` is
     dockerignored, so Cloud Run falls through to ADC and calls as the *compute* account. Sharing
     with only the key-file account gives a setup that works locally and 403s in production
     (`"The caller does not have permission"` on `sheets.googleapis.com`). Share with both.
  3. **Register it in `config.FORM_SOURCES`** — this is the *only* place a form is linked:
     ```python
     "linear-algebra/hw2": {
         "sheet_id":  "<the responses spreadsheet id>",
         "tab":       None,                    # None = first tab
         "id_column": "ID",                    # header of the 9-digit ID column
         "files":     {"Transcription": "hw2.md"},   # sheet column -> stored filename
     },
     ```
     The stored filename comes from here, never from Drive: Forms appends the submitter's
     display name to every upload (`hw2 - Shachar.md`), so Drive names are not stable.
     Adding the entry is also what routes the assignment to Forms and sets its identity mode —
     there is no second switch.
  4. **Add the assignment resources** under `backend/assignments/<course>/<name>_readme.md` and
     `_question_pool.json` (see `backend/assignments/README.md`; the namespaced name creates the
     subdirectory for free), plus an `ASSIGNMENT_LABELS` entry.
  5. **Deploy the course's own Cloud Run service** with `COURSE_ID=<course>`. Do NOT set
     `COURSE_ID` on an existing course's service — it switches that course's prompts too.

  Verify from the logs: `[session:start] … source=google_form student_key='id:...'`.

- **Add a field to a session/grade.** Add the column in `models.py`, write a migration script in `backend/scripts/` (see `migrate_add_grade_email_sent.py` as the pattern), populate it where it's produced, and surface it in `schemas.py` + the relevant admin view.
- **Add/modify an examiner behavior.** Edit `backend/prompts/examiner_prompt.txt`. If it needs new structured output, extend `ExaminerOutput` in `agents.py` (it auto-becomes part of the forced tool schema) and handle the new field in the `/api/exam/answer` logic.
- **Add an admin view.** Add a guarded endpoint in `main.py` (use `_require_admin`), register it **before** the `/api/admin/results/{github_username}` wildcard, add a proxy route under `src/app/api/admin/...`, and a page under `src/app/admin/...`.
- **Change scoring weights or the bonus.** Weighting lives in `compute_final_grade` (`agents.py`); the student-facing bonus lives in `grade_email_template.py` (`ADAPTATION_BONUS_POINTS`). The IRT placement tables live in the grader/code-reviewer prompts.
- **Add an integration (Sheets/Calendar/etc.).** Follow `google_apis.py`: read credentials via the existing `_credentials()` resolver, add a typed helper, call it from `main.py` admin/cron logic.

**Deploy:** `cloudbuild.yaml` builds the backend image + the frontend image and deploys backend (`ai-exam-backend-ex1`) and the three frontend variants to Cloud Run in `me-west1` (and `europe-west1`). Frontend duration/QA flags are build args; backend secrets are Cloud Run env vars. The backend Docker image runs `uvicorn main:app` on `:8080`.

### 14.1 Multi-course deploys

All course services share **one** `backend:latest` image; a course is a different `COURSE_ID`, not
a different build.

**Four triggers fire on master, each filtered by path — this is the thing to get right:**

| Trigger | Config | `includedFiles` | Deploys |
|---|---|---|---|
| `deploy-on-push` | `cloudbuild.yaml` | `backend/**`, `courses/**`, `cloudbuild.yaml` | both backends |
| `deploy-on-push-fe-ex1` | `cloudbuild-frontend-ex1.yaml` | `frontend/**` | `exam-frontend-ex1`, `exam-admin`, `exam-frontend-la` |
| `deploy-on-push-fe-prod` | `cloudbuild-frontend-prod.yaml` | `frontend/**` | `exam-frontend` |
| `deploy-on-push-fe-qa` | `cloudbuild-frontend.yaml` | `frontend/**` | `exam-frontend-qa` |

**A service must be deployed from the pipeline whose filter sees its changes.** The LA frontend
originally went into `cloudbuild.yaml`, which never fires on a frontend-only commit — so it would
have kept serving stale code exactly as if it had never been added. `courses/**` is in
`deploy-on-push` because the profiles are baked into the backend image: a prompt edit with no
backend change still needs a rebuild, and without that entry nothing fires at all.

**Adding a course.** Two steps, `--image` and `--region` only, in the two matching pipelines:

```yaml
  - name: 'gcr.io/cloud-builders/gcloud'
    args: [run, deploy, ai-exam-backend-<course>,
           --image=me-west1-docker.pkg.dev/ai-examiner-system/ai-examiner-system-repo/backend:latest,
           --region=me-west1]
```

Three properties that are deliberate, not incidental:

- **Course steps go first, not last.** Steps run in order and a failure skips everything after it.
  `exam-frontend-ex1` and `exam-admin` are deployed by *two* pipelines, so they survive losing a
  race; the course services have no second path and must not sit behind the contended steps.
- **No `--update-env-vars` on course steps.** `COURSE_ID` and the secrets live on the service and
  a deploy preserves them. Setting them in the pipeline would silently revert a change made
  directly to the service — e.g. switching `COURSE_ID` from `linear-algebra-TEST` to the real
  profile. (If you ever do set env there, use `--update-env-vars`, never `--set-env-vars`: the
  latter replaces the whole set and drops `COURSE_ID`, reverting the service to legacy prompts.)
- **Push is enough; don't also run `gcloud builds submit`.** The `deploy-on-push` trigger runs the
  same file, and two concurrent builds make the loser die with `ABORTED: Conflict for resource`.

**If a service is ever deployed outside the pipeline**, remember Cloud Run pins `:latest` to a
digest at deploy time — a running revision never picks up a later push of the same tag, and the
symptom is silent (the service happily serves stale code). Check `status.latestReadyRevisionName`:
a service still on `-00001` after several builds has never been redeployed.

### 14.2 Course scoping: two traps

**`COURSE_ID` names a folder; `FORM_SOURCES` keys carry an assignment namespace.** They only
coincide by convention. `COURSE_ID=linear-algebra-TEST` against key `linear-algebra/hw1` matched
nothing, so the registry narrowing no-opped and the service kept the **OS** registry — offering
`assignment-2` under Linear Algebra prompts, with `[AdminCache] startup warm for 'assignment-2'`
as the only trace. `COURSE_ASSIGNMENT_NS` now carries the namespace (default: `COURSE_ID` minus
`-TEST`), and a `COURSE_ID` matching no assignment **raises at startup** rather than falling back.

**Startup maps are gated on what makes each relevant**, not on `COURSE_ID` blanket-style:

| Startup work | Gate | Why |
|---|---|---|
| `_validate_github_usernames()`, `_load_username_fallback_map()` | `serves_github(KNOWN_ASSIGNMENTS)` | Both bridge a github_username to an ID — meaningless on the Forms path. Gated on intake, since a future course could use GitHub. |
| `_load_assignment_map()` | `not COURSE_ID` | Splits one cohort across assignments; other courses have everyone do everything. |
| `_load_id_mapping()` | `not COURSE_ID` or `ID_MAPPING_GCS_PATH` set | OS needs a roster (a repo carries no name). A course loads one only if it points the path itself — otherwise it would silently load the OS roster from the default. |

A course that wants a roster just sets `ID_MAPPING_GCS_PATH`; no code change. Linear Algebra sets
nothing and takes the name from the form (MULTI_COURSE_MIGRATION §4.4a).

**A new course's assignment overview reads 0 until `ResultSummary` is populated.** The dashboard
calls `/results/aggregate_fast`, which reads the `ResultSummary` table and nothing else — the
blob-backed `/aggregate` it was designed to fall back to **has been removed**, so the
`{"empty_table": true}` it returns has no fallback and the page just renders `count: 0`. That
table is written only by the grader funnel behind `RESULT_SUMMARY_ENABLED`, which is **not set by
default**, so a new course silently shows an empty dashboard while every per-student page works.

For each new course: set `RESULT_SUMMARY_ENABLED=true`, then populate the rows for sessions that
already exist — `backend/scripts/backfill_result_summary.py --assignment <name>` (needs Cloud SQL
reachability), or re-grade those sessions through the admin, which runs the same funnel.

Recognise it by the asymmetry: **per-student results render fully, the overview shows 0 examined
and blank averages.** That combination means the blobs are fine and only the derived table is
missing.

**Do not remove `PYTHONUNBUFFERED=1` from the Dockerfile.** Without it `print()` output
(`[prompts]`, `[session:start]`) sits in a block-buffered stdout until 8 KB accumulates while
uvicorn's stderr logging flows freely, so a low-traffic service looks like it logged nothing.

**Tests:** `backend/tests/` has pytest coverage for the distress flow and timeout metadata — run these after touching `/api/exam/answer`, `/api/exam/timeout`, or the distress logic.
