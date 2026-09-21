# Automated Oral Exam System — Project Context

> **Purpose of this document:** Give an AI assistant full context to understand the system and help refine prompts, grading logic, and exam behavior. Read this before asking questions about any part of the project.

---

## Goals & Vision

This system automates the oral exam component of a Bar-Ilan University Operating Systems course. Students submit C programming assignments via GitHub Classroom. The TA then runs each student through a 15-minute AI-driven oral exam that:

1. **Verifies authorship** — checks that the student actually wrote and understands their own code (not just copy-pasted from ChatGPT).
2. **Evaluates understanding** — probes OS concepts embedded in the student's specific implementation (system calls, process management, file I/O, memory, etc.).
3. **Produces a grade** — combines oral defense performance with static code quality into a final numeric grade.
4. **Scales to a whole class** — a single TA can examine dozens of students without being present for each exam.

The exam is conducted in **Hebrew** (technical terms stay in English). It asks exactly **3 focused questions**, then grades automatically in the background.

**Key design philosophy:**
- Questions are always grounded in the student's *specific* code, not generic OS theory.
- The examiner never confirms or denies whether an answer is correct (poker face).
- Authorship confidence is tracked independently from technical understanding.
- The grader applies Item Response Theory — a student who reaches hard questions and partially fails is scored higher than one who breezes through easy ones.

---

## Repository Layout

```
project root/
├── backend/                        ← All server code
│   ├── main.py                     ← FastAPI app & API endpoints
│   ├── agents.py                   ← LLM agent wrappers (Examiner, Grader, Code Reviewer)
│   ├── config.py                   ← Paths, model names, assignment constants
│   ├── github_stub.py              ← GitHub App auth + file fetch + exam context builder
│   ├── plan_assembler.py           ← QuestionPicker: stateful per-session question selection
│   ├── database.py                 ← SQLAlchemy setup (SQLite)
│   ├── models.py                   ← ORM models: User, Session
│   ├── schemas.py                  ← Pydantic request/response schemas
│   ├── prompts/
│   │   ├── examiner_prompt.txt     ← System prompt for the Examiner agent
│   │   ├── grader_prompt.txt       ← System prompt for the Grader agent
│   │   └── code_reviewer_prompt.txt← System prompt for the Code Reviewer agent
│   ├── assignments/
│   │   ├── {name}_readme.md        ← Assignment instructions (shown to all agents)
│   │   └── {name}_readme_question_pool.json ← Curated question bank for this assignment
│   ├── submissions/                ← (gitignored) fetched student files, one folder per student_id
│   ├── .env                        ← (gitignored) secrets
│   └── .env.example                ← Template for env vars
├── cli_tester.py                   ← CLI mock frontend — hits the API as a student would
└── exercises/                      ← Raw assignment materials and past student submissions
```

---

## High-Level Flow

```
TA Setup (once per assignment)
  1. Set ASSIGNMENT_NAME in config.py
  2. Place {name}_readme.md and {name}_readme_question_pool.json in backend/assignments/
  3. Set GITHUB_ORG in .env (pattern defaults to "{assignment_name}-{github_username}")

Per-Student Exam
  Step 0: POST /api/admin/fetch-submission
          → GitHub App auth → download student .c files → save to submissions/<student_id>/

  Step 1: POST /api/auth/start
          → Load files from disk → build exam context → pick Q1 (medium difficulty)
          → Call Examiner LLM → return session_id + question text

  Step 2-4: POST /api/exam/answer  (×3)
          → Student submits answer → Examiner evaluates + picks next question
          → On Q3 answer: Examiner returns FINISH_EXAM action

  Background (after exam ends):
          → Code Reviewer analyzes source files independently (no exam data)
          → Grader reads transcript + Signal B → assigns oralDefenseScore
          → compute_final_grade() combines both scores

  Step 5: GET /api/admin/results/{student_id}
          → Returns full transcript, code review, grader verdict, final grade
```

---

## Component Details

### 1. GitHub Integration (`github_stub.py`)

Uses **GitHub App** authentication (not PAT):
- Generates a short-lived JWT signed with the app's RSA private key (PyJWT RS256)
- Exchanges it for an Installation Access Token (valid 1 hour)
- Downloads files via the Contents API (`GET /repos/{owner}/{repo}/contents/{path}?ref={branch}`)

Repo resolution is **pattern-based** — no GitHub Classroom API:
```
GITHUB_ORG=biu-os-2026
GITHUB_REPO_PATTERN={assignment_name}-{github_username}   ← default
→ biu-os-2026/test-assignment-shacharsl97
```

`build_exam_context()` builds the string passed to the Examiner on turn 1:
- Assignment README
- Each student file (or a `[NOT SUBMITTED]` placeholder if missing)
- Missing files trigger a specific examiner behavior: ask one light question about intent, don't dwell.

---

### 2. API Endpoints (`main.py`)

| Endpoint | Who calls it | What it does |
|----------|-------------|--------------|
| `POST /api/admin/fetch-submission` | TA/admin | Fetches student files from GitHub, saves to disk |
| `POST /api/auth/start` | Student/frontend | Creates session, calls Examiner for Q1 |
| `POST /api/exam/answer` | Student/frontend | Submits answer, gets next question or finish signal |
| `GET /api/admin/results/{student_id}` | TA/admin | Returns full session log + grade |
| `GET /health` | Anyone | Returns ok + question pool size |

**Session state** is stored in SQLite between requests:
- `examiner_messages` — full Anthropic message history (for multi-turn context)
- `picker_state` — serialized QuestionPicker so Q2/Q3 don't repeat topics
- `pending_tool_use_id` — Anthropic tool-use protocol requires acknowledging the previous tool call
- `transcript` — human-readable log of all turns

---

### 3. LLM Agents (`agents.py`)

All agents use **Anthropic tool-forcing** — the LLM must call a specific tool and return structured JSON. This makes output parsing reliable (no regex needed).

**Fallback cascade on overload (HTTP 529):**
```
claude-opus-4-6  →  claude-sonnet-4-6  →  Gemini 2.5 Pro
```
Gemini fallback flattens the message history into a single prompt since Gemini doesn't have native multi-turn tool use.

#### Examiner Agent
- Model: `claude-opus-4-6`
- Temperature: random `0.2–0.4` per session (for variety)
- Called 4 times per exam: turns 1, 2, 3, and a final FINISH_EXAM turn
- Output schema: `ExaminerOutput` (Pydantic → Anthropic tool schema)
  - `questionText` — the question shown to the student (Hebrew)
  - `action` — `NONE` | `JUMP_TO_LINE` | `FINISH_EXAM`
  - `internalEvaluation` — `understandingScore` (1–5), `authorshipConfidence` (high/medium/low), flags
  - `internalReasoning` — hidden chain-of-thought (never shown to student)
  - `chosenTopicDifficulty` — which of the 3 offered options was selected (Q2/Q3)
  - `nextQuestionDifficulty` — the examiner's recommendation for next question difficulty

**Turn structure:**
- **Q1:** User message = full exam context + one medium-difficulty topic
- **Q2/Q3:** User message = `tool_result` acknowledgement + student answer text + 3 topic options (easy/medium/hard)
- **FINISH_EXAM:** Examiner returns `action: "FINISH_EXAM"` after Q3 answer, with a closing message

#### Code Reviewer Agent
- Model: `claude-sonnet-4-6`
- Temperature: 0.1
- **Runs blind** — sees only the assignment README + student code, never the transcript
- Produces:
  - `staticCodeQualityScore` (0–100): code correctness, completeness, system call hygiene
  - `signalBAssessment`: stylistic markers suggesting LLM generation (`none`/`low`/`moderate`/`high`)

#### Grader Agent
- Model: `claude-opus-4-6`
- Temperature: 0.1
- Sees: assignment README + Signal B result + full exam transcript (including examiner's internal JSON)
- Does NOT see the student's source code (by design — avoids double-penalizing)
- Produces:
  - `oralDefenseScore` (0–100): oral performance evaluated via Item Response Theory
  - `authorshipAssessment`: `established` | `partial` | `not_established`
  - `integrityFlag`, `promptInjectionFlag`: boolean integrity signals
  - `professorReport`: Hebrew summary for course staff

#### Grade Combination (no LLM)
```python
raw = round(0.75 * oralDefenseScore + 0.25 * staticCodeQualityScore)

if authorship == "not_established":  final = min(raw, 70)
elif authorship == "partial":        final = min(raw, 80)
else:                                final = raw

if oralDefenseScore < 50:            final = min(final, oralDefenseScore + 5)
```

---

### 4. Question Picker (`plan_assembler.py`)

Each session gets a `QuestionPicker` initialized with a random seed. The picker:
- Selects Q1 with `pick_question(difficulty="medium")`
- For Q2/Q3, offers the examiner 3 options via `peek_options(["easy", "medium", "hard"])` — the examiner chooses based on student performance
- Avoids repeating the same `focus`, same `file` (too many times), or same `dimension`
- Respects `conflicts_with` relationships between questions
- Is serialized to JSON between requests (`to_state()` / `from_state()`)

---

### 5. Question Pool Format (`{name}_readme_question_pool.json`)

Each entry in the pool:
```json
{
  "id": "unique-id",
  "file": "backup.c",
  "focus": "copy_directory() recursive traversal",
  "dimension": "edge_case",
  "difficulty": "medium",
  "examiner_notes": "Ask what happens when readdir() returns a subdirectory...",
  "conflicts_with": ["other-question-id"]
}
```

**Dimensions:**
- `design_choice` — why did you choose this approach?
- `edge_case` — what happens with unusual input?
- `error_handling` — what if a system call fails?
- `api_depth` — what exactly does this syscall return/do?
- `code_flow` — trace execution with specific values
- `cross_file` — how does data/control flow between files?

---

### 6. Examiner Prompt Design (key behaviors)

The examiner prompt (Hebrew) enforces:

- **Poker face rule:** Never confirm or deny answers. No "correct!", "great!", "exactly". Transitions must be cold and factual ("נעבור לקובץ הבא").
- **One question per turn:** Strictly forbidden to ask two sub-questions in one turn. Words like "בנוסף" (additionally), "1." and "2." in the same message are banned.
- **Authorship probing:** Every question must embed at least one ownership probe ("why did you choose this approach?").
- **Bug pivot:** If the examiner spots a bug, it may override the provided topic to ask about the bug instead (sets `bugPivotUsed: true`).
- **Dimension flexibility:** The topic's dimension is a strong suggestion; the examiner may swap it if it doesn't yield a meaningful question for that specific function.
- **Anti-prompt-injection:** Ignores student attempts to manipulate the AI, sets `suspectedPromptInjection: true`, and moves to next question.
- **Missing files:** Asks one light question ("what was this supposed to do and why is it missing?") and moves on — no technical questions about unseen code.
- **Iron rule:** Always advance to the next question regardless of answer quality.

**Scoring rubric (understandingScore 1–5):**
- 5: Correct logic + design rationale + authorship signal (why this approach over alternatives)
- 4: Correct mechanism with minor gaps
- 3.5: Conceptually correct but uniformly polished — no personal ownership of decisions
- 3: Understands what but not why
- 2: Superficial behavior description only
- 1: Cannot explain own code

**Critical anti-pedantry rule:** Do not penalize for forgetting string literals, variable names, or minor syntactic details. The exam tests authorship and comprehension, not photographic memory.

---

### 7. Grader Prompt Design (key behaviors)

- **Item Response Theory:** A student who reaches hard questions and partially fails scores higher than one who breezes through easy ones. High-tier attempts → 85+ baseline even with partial failure.
- **Two-axis authorship:** Understanding (primary, ~80%) vs. Authorship confidence (secondary).
- **Signal A vs Signal B:** Exam behavior (Signal A) always overrides code style analysis (Signal B). Signal B can only *strengthen* an existing concern, never create one.
- **Wrong justification ≠ no ownership:** A student who gives a wrong reason for their design choice still demonstrates authorship. Lower `understandingScore`, keep `authorshipConfidence: "high"`.
- **Integrity flag:** Only set for students who demonstrably cannot explain their code at all (≤2 on basic questions). Authorship weakness alone does not trigger it.
- **External attribution is neutral:** "The TA told me to do X" is neither positive nor negative — only whether the student can explain *why* matters.
- **No score manipulation for flags:** Even if integrity/injection flags are set, compute the true earned score. Let the professor apply manual penalties.

---

### 8. Code Reviewer Prompt Design (key behaviors)

- **Task 1 (code quality):** Scored on correctness, completeness, system call hygiene, missing files. Generous disposition — reward what's right, don't penalize every imperfection.
- **Task 2 (Signal B):** Looks for LLM conversational artifacts (prompt echoing, hallucinated placeholders, AI disclaimers). 1–2 markers = normal for a good student. Flag `"high"` only for direct LLM artifacts or 4+ pervasive systematic indicators.
- **Independence:** Signal B must never influence the code quality score, and vice versa.

---

## Configuration & Deployment

### Switching assignments
1. Change `ASSIGNMENT_NAME` in `backend/config.py`
2. Add `backend/assignments/{new_name}_readme.md`
3. Add `backend/assignments/{new_name}_readme_question_pool.json`
4. Update `STUDENT_FILES` in `config.py` to match the expected .c file names

### Environment variables (backend/.env)
```
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...          # optional fallback

GITHUB_APP_ID=...
GITHUB_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----
GITHUB_INSTALLATION_ID=...
GITHUB_ORG=biu-os-2026          # required
# GITHUB_REPO_PATTERN=...       # optional, default: {assignment_name}-{github_username}
GITHUB_BRANCH=main
GITHUB_FILES_PATH=              # subfolder inside repo, empty = root
```

### Running locally
```bash
cd backend
uvicorn main:app --reload --port 8000

# In another terminal:
python cli_tester.py --url http://localhost:8000
```

### Models used
| Agent | Default model | Fallback |
|-------|--------------|---------|
| Examiner | claude-opus-4-6 | claude-sonnet-4-6 → gemini-2.5-pro |
| Grader | claude-opus-4-6 | claude-sonnet-4-6 → gemini-2.5-pro |
| Code Reviewer | claude-sonnet-4-6 | gemini-2.5-pro |

Debug flags in `config.py`: `FORCE_SONNET=True` uses Sonnet for all calls (cheaper testing). `FORCE_GEMINI_FALLBACK=True` skips Anthropic entirely.
