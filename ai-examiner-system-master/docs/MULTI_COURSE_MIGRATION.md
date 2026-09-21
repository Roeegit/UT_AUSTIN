# Multi-Course Migration — working plan

> **Status: WORKING DOCUMENT.** This is the single file for everything about running more
> than one course on the system. Add migration notes, ideas, and open questions here rather
> than starting new files.
>
> **Nothing in §4 onward has been implemented.** Today the system runs exactly one course.
> `courses/` currently holds prompt material only and is not wired into the backend.
>
> Last updated: 2026-08-12

---

## 1. The one-line summary

The system has **no concept of a course**. It has a concept of an *assignment*, and every
assignment is assumed to belong to the same course. Adding a second course means
introducing that concept — in configuration, in the data model, and in the operational
surfaces.

The prompt layer is already solved (§3). The rest is not.

---

## 2. What is already done

| | Status |
|---|---|
| Course-agnostic prompt skeletons (`courses/_shared/`) | ✅ done |
| Course profile format + renderer (`courses/render.py`) | ✅ done |
| OS profile as worked example, rendered and diffed against live | ✅ done |
| Guide for new course staff (`FOR_NEW_COURSES.md`) | ✅ done |
| **`result_summary` table + funnel + fast admin endpoint (§4.10)** | ✅ **LIVE** — backfilled (467 rows), `RESULT_SUMMARY_ENABLED=true`, dashboard reads `/aggregate_fast`; old `/aggregate` removed |
| **Item-analysis / divergence tooling (§4.8)** | ✅ **LIVE** — nightly Cloud Run Job (23:00) + `/item-analysis` endpoint + admin dashboard panel |
| **Second code-reviewer validator (§4.9)** | ✅ **LIVE** — `REVIEWER_VALIDATOR_ENABLED=true`, grade-correcting, Opus, verified on a real session |
| Admin dashboard latency fixes (fast-only, non-blocking calendar) | ✅ **LIVE** (2026-07-22) |
| Cold-start-friendly student error message | ✅ done (2026-07-23) |
| Backend reads prompts from `courses/<id>/rendered/` (§4.1) | ❌ not started |
| Everything else below | ❌ not started |

> **Deployed 2026-07-21/22.** The three features above are enabled on the live OS backend —
> validated on real sessions (validator ran 95→95 clean; funnel upserts; `/aggregate_fast`
> ~0.3s). The remaining `❌` items below are the multi-course work proper, most of it blocked
> on the §3 scoping decision (department).

---

## 3. The blocking design decision — how is a course scoped?

Everything else depends on this. Two viable options:

### Option A — one deployment per course
Each course gets its own Cloud Run services and its own database. `COURSE_ID` is baked into
the deployment; the code barely changes.

- ✅ Strong isolation — no chance of cross-course data leakage or an admin seeing another
  course's students. Attractive given the PII involved.
- ✅ Smallest code change by far. Mostly a deploy-config exercise.
- ✅ Courses can run different system versions (one can pilot a change without risking the other).
- ❌ Cost multiplies per course (though min-instances=0 makes an idle course nearly free).
- ❌ N databases, N migrations, N secret sets to keep in step.
- ❌ No cross-course view — "did this student sit exams in both courses?" becomes impossible.

### Option B — one deployment, `course_id` column throughout
A single system serves all courses; every query filters by course.

- ✅ One deployment to operate, one migration path, one admin surface.
- ✅ Cross-course analytics possible (directly useful for the correlation study).
- ❌ Every query must filter correctly. **One missed filter is a privacy incident.**
- ❌ Schema migration on a live table; admin surface needs a course selector everywhere.

**Recommendation: Option A for the first additional course.** The isolation argument is
strong for student PII, the code change is small enough to do before a semester starts, and
it does not foreclose Option B later. Revisit at three-plus courses, when operating N
deployments becomes the dominant cost.

**STATUS: ON HOLD — waiting on the department.** The decision partly depends on physical
capacity: whether there is another room and machine available for supervised examining. If
the department can only support one exam room, courses must be time-sliced anyway and the
"one deployment each" cost argument weakens considerably. **Do not start implementation
until this comes back.**

Note also that the student-facing shape follows from this choice: two separate deployments
means two URLs, whereas a shared deployment means the student picks their course on entry
(one more button on the lookup screen). That is worth deciding deliberately rather than
inheriting from the infrastructure choice.

---

## 4. Concrete changes required

### 4.1 Prompts — small, ready to do

Prompts load from three constants at `backend/main.py:504-506` via `config.py`.

- Add `COURSE_ID` to `config.py` (env-overridable).
- Repoint `EXAMINER_PROMPT_PATH`, `GRADER_PROMPT_PATH`, `CODE_REVIEWER_PROMPT_PATH` at
  `courses/<COURSE_ID>/rendered/`.
- Add `python courses/render.py <course> --check` to the build so a stale render fails the
  deploy rather than shipping.

### 4.2 Assignment registry — **name collision is a real risk**

`config.py` keys everything off bare assignment names: `ASSIGNMENT_FILES`,
`ASSIGNMENT_LABELS`, `KNOWN_ASSIGNMENTS`, `ASSIGNMENT_REPO_PATTERNS`, `DEFAULT_ASSIGNMENT`,
`LATEST_ASSIGNMENT`.

Two courses will both plausibly have an assignment called `assignment-1`. Under Option B
that silently collides in the DB, in GCS, and in retake-prevention. Under Option A it is
harmless but still confusing in exports.

**→ Namespace assignment IDs as `<course>/<assignment>` regardless of which option is chosen.**
Cheap now, painful later.

**Plan: do this for next semester's assignments**, applying the new scheme to new
assignments as they are created rather than migrating the 2026 rows. Implementation is
easier once §3 is settled — under Option A the namespace is mostly cosmetic (useful for
exports and for merging data later), while under Option B it is load-bearing and must be
enforced at every query. Either way, adopting the *naming convention* now costs nothing and
means the 2027 data is already correctly shaped whichever way §3 lands.

### 4.3 Data model

`Session.assignment_name` (`models.py:49`) is the only scoping field. There is **no course column**.

`User`'s primary key is `github_username` (`models.py:20`) — global. A student taking both
courses is one row. Under Option B this is arguably correct; note that any per-user lock
(the complaint lock, retake prevention) then spans courses unless explicitly scoped.

**Retake prevention** keys on (username, assignment). With colliding assignment names,
finishing OS `assignment-1` could block Intro-CS `assignment-1`. **This is the sharpest
concrete bug in the current design.**

### 4.3b Exam shape (3 questions × 5 min) — **must be checked per course**

"Three questions" is not a setting. It is baked into **three separate layers**, and they
would all have to move together.

**Layer 1 — the grader prompt.** Two rules are numerically calibrated to three questions:

1. **The IRT placement table** maps (average score × difficulty profile) → a score range.
   The difficulty profile — "Reached HARD" / "All MEDIUM" / "Includes EASY" — is derived
   from a 3-question trajectory.
2. **The authorship table** is a set of *pattern* rules over the per-question confidence
   values: "at least 1 high → established", "2 or more low → not_established". At 2
   questions, "2 or more low" silently means *both*, a far harsher rule. At 4, it becomes
   more lenient than intended.

**Layer 2 — the examiner prompt** (`courses/_shared/examiner_skeleton.txt`). The structure
is written around exactly three turns:

- Line 3 states "a 15-minute, 3-question oral exam".
- "How Questions Are Provided" splits into **Question 1** (two medium options, difficulty
  fixed at medium) and **Questions 2 and 3** (six options, two per difficulty). A different
  count needs a different opening/continuation split.
- The field logic repeats the split: `chosenTopicLabel`, `chosenTopicDifficulty`, and
  `nextQuestionDifficulty` are each specified as "on Q1 … / on Q2 or Q3 …", and
  `understandingScore` must be null on turn 1.

**Layer 3 — the backend, and this is the real blocker.** `main.py:1205` and `main.py:1385`
both clamp with a literal `min(..., 3)`. Changing the exam shape is therefore a **code**
change, not just a prompt change — a course configured for 4 questions would silently have
question 4 relabelled as question 3.

Good news: `QuestionPicker.peek_options()` takes a difficulty list, so the picker itself is
already count-agnostic. The clamps and the prompts are the constraint.

**→ This is a CHECK, not a work item.** For each new course, ask what its questions-per-exam
and time-per-question will be:

- **If they keep 3 × 5 min** (the likely case — it is what we recommend and it worked well):
  **nothing to do.** All three layers are already consistent.
- **Only if they diverge:** all three layers must be changed together, and a mismatch
  between them is worse than any single one being wrong.

The risk being guarded against is a course changing the count without telling us — that is a
silent fairness regression rather than a visible error, which is why it belongs on a
pre-launch checklist. Note that layer 3 fails *quietly*: a fourth question is relabelled,
not rejected.

**Deferred — do not build speculatively.** If a course does diverge, the clean fix is to
make the exam shape a declared input rather than an assumption: add `QUESTIONS_PER_EXAM`
and `SECONDS_PER_QUESTION` to the course profile, have the examiner skeleton describe
"question 1 vs. subsequent questions" instead of naming Q2 and Q3, express the grader's
authorship rules proportionally ("more than half were low") rather than by count, and
replace the `min(..., 3)` clamps with the configured value. **Not worth doing for a
hypothetical** — revisit only when a course actually asks for it.

### 4.3c Submission intake — **GitHub is an assumption, not a given**

The system currently assumes GitHub Classroom end to end: `github_stub.py` resolves and
fetches the repo, `ASSIGNMENT_REPO_PATTERNS` names it, and the whole `GITHUB_*` env block
configures it.

**Mathematical courses will very likely not use GitHub at all.** They may use Moodle, a
shared Drive folder, or direct upload. So intake has to become pluggable: GitHub is one
adapter, and at least one non-GitHub adapter (Drive folder or direct upload) is needed.

> **The deeper problem: `User.github_username` is the primary key** (`models.py:20`), and
> `Session.github_username` is the foreign key. GitHub identity is wired into the data model,
> the retake lock, the roster join, the admin lookup, and the result blob path
> (`results/{assignment}/{github}.json`). A course without GitHub has **no value for the
> column that identifies a student.**
>
> This is a larger change than the prompt work and probably larger than the course scoping.
> It means introducing a course-neutral student key — university ID or email — with the
> GitHub username demoted to one optional identifier among several.
>

**Position to take with course staff: strongly recommend GitHub Classroom.** Not as a
preference — as the difference between "configuration" and "a development project with
schedule risk." We migrated to it ourselves this semester; it went smoothly, did not take
long, and students adapted well (several preferred it to the previous method, and it is a
skill they need anyway).

Git is content-agnostic — a repo holds PDFs, `.tex`, notebooks, or anything else — so
"we don't write code" is not a reason it cannot work.

> **But GitHub solves intake, not anchoring.** If a course pushes only a *compiled PDF*, we
> have the submission but still cannot line-anchor questions in it (Tier C, §2 of the course
> guide). If they push the **source** — `.tex`, `.md`, `.ipynb` — both problems are solved
> at once. **The ask is therefore "GitHub Classroom, source files committed," not just
> "GitHub."**

If a course genuinely cannot adopt it, we need a new intake adapter plus the identity rework
above. That is real development with real schedule risk, and it should be presented to them
as such — honestly, not as pressure — so the tradeoff is theirs to make with open eyes.

### 4.3d Examiner changes already made in the skeleton — **each needs code to follow**

These are done in `courses/_shared/examiner_skeleton.txt` but are **not** reflected in the
backend or frontend, which still speak the old names. They must be applied together when
§4.1 wires the rendered prompts in.

**1. `codeLine` → `fileLine`** (de-coding the field name). Eight sites:

| File | Line |
|---|---|
| `backend/agents.py` | 47 — `codeLine: Optional[str]` |
| `backend/main.py` | 1209, 1389 — `action_params.get("codeLine")` |
| `frontend/.../lib/types.ts` | 32 |
| `frontend/.../components/CodePanel.tsx` | 26 |
| `frontend/.../components/CodeViewer.tsx` | 16–18 (`findCodeLine`) |
| `frontend/.../hooks/useExamState.ts` | 341, 449 |

The backend↔frontend wire field is `action_code_line`; rename it in the same pass or the
two halves disagree. **A mismatch here silently disables line highlighting** — the exam
still runs, the student just never sees the line, so it will not show up as an error.

**2. `bugPivotUsed` → `errorPivotUsed`.** Only one code site: `backend/agents.py:65`. Nothing
reads it programmatically; it is recorded for audit. Historical blobs keep the old key, so
any future analytics over it must accept both spellings.

> **Naming note:** `errorPivotUsed` was chosen over `errorFound` deliberately. The field does
> not record "an error exists" — it records that *the examiner overrode the offered topic*,
> which is what makes an audit trail explicable when the asked question does not match any
> question the picker offered. `errorFound` would lose that meaning.

**3. The submission reviewer now expects the SKELETON as a third input — the backend does
not yet send it.** This is the one change on this list with a live fairness payoff, and it
is a backend change, not just a prompt change.

The reviewer currently receives only the assignment instructions and the student's
submission. It therefore **cannot tell which parts the student wrote**, so it judges provided
material as if the student authored it. That is precisely the 2026 failure mode: 104 students
lost marks for not checking the return value of a provided `static inline void` helper, and
36 for a `volatile` qualifier the spec mandated — both upheld on appeal.

The skeleton now instructs the reviewer that provided material is never assessed and that
spec-mandated constructs are correct by definition. **For that to bite, `main.py` must
actually load the starter material and pass it into the code-reviewer call.**

> **Blocker found 2026-07: the provided files are not stored anywhere the backend can load.**
> `{assignment}_files.json` lists only the *student* files to fetch; provided headers like
> `common.h` (which defines the `void write_all` that caused the 104-student false positive)
> are deliberately NOT fetched and NOT stored. So this is a **data task before a code task**:
> per assignment, collect the provided/skeleton files (from the GitHub Classroom template
> repo) and store them — e.g. `backend/assignments/{assignment}_skeleton/` or a GCS prefix —
> then load them like `load_assignment_inputs` does the student files and pass as
> `skeleton_files` to both `call_code_reviewer` and `call_reviewer_validator`.

**Interim mitigation (shipped):** the reviewer validator (§4.9) now catches the main case
without the skeleton, via the "penalized a call to a function not defined in the submitted
files → probably provided → challenge it" heuristic. This is a guard, not a substitute —
storing the real skeleton is still the correct fix, especially for a new course.

The reviewer prompt degrades safely if the skeleton is absent (told to assume the student did
*not* author anything ambiguous), so shipping the prompt before the data work is harmless.

**4. The missing-file question was removed.** The examiner previously spent a question asking
"what was this file supposed to do and why wasn't it submitted?". It is now instructed to
ignore `[NOT SUBMITTED]` markers and ask a normal question instead.

Rationale: the marker does not reliably mean the student failed to submit — it also fires
when the per-assignment file list is wrong for that student. This already happened in 2026
(see the comment at `config.py:50-52`, where `id.txt` had to be removed from the
assignment-3 file list to stop every student being asked why they had not submitted a file
the spec never required). Spending one of only three questions on a false premise is a
material fairness cost for very little signal.

**This does not stop missing work being penalised** — the submission reviewer still treats
`[NOT SUBMITTED]` as a missing deliverable at 10–15 points each, which is the correct place
for it: the static score, not the oral exam.

But - please penalize it more deeply than before. add a few points penalty for it more than it does today.

**→ When this goes live, update `SYSTEM_QUALITIES.md` capability #24**, which documents the
old behaviour. It is accurate for the currently-running system, so leave it until then.

### 4.3e Math-course transcription + verification surface — **OPTIONAL, course-dependent**

> **Execution plan for the first such course lives in `docs/LINEAR_ALGEBRA_PLAN.md`** (2026-08-03):
> sequenced phases, the `student_key` identity design, the `SubmissionSource` adapter, the
> MathViewer anchoring mechanics, the staff-meeting agenda, and the blocked-items table with
> owners. This section stays the decision record; that file is the schedule. Artifacts already
> written: `courses/_shared/transcription_prompt.txt` and `courses/_poc/verify_render.html`.

For a math course (e.g. linear algebra) students hand-write, then use *their own* LLM to
transcribe the photo into **line-/step-numbered Markdown with inline LaTeX math** (`$…$`) —
**not** a compiled PDF. Rationale (decided 2026-08): the exam anchors questions to a line
(`fileLine`), which needs line-addressable *source*; a compiled PDF is displayable but not
cleanly anchorable, and LaTeX math extracts unreliably from a PDF text layer (fine on prose,
flaky-to-broken on equations, dead on scanned images). Source is the deterministic, cheaper
path; PDF is a **documented downgrade fallback**, not a lateral swap.

**Accountability without LaTeX literacy.** Students never read/write LaTeX. They verify the
**rendered** view (typeset math + visible step numbers) against their photo and flag
mismatches *by step number*; the correction loop goes back through their LLM. "Requiring
source" means only "submit the text your LLM produced, not a compiled PDF" — a lighter action,
so the usual "first-years can't do LaTeX" objection does not apply. Format is Markdown+`$…$`,
not full `.tex` (no preamble/compile). The transcription prompt (faithful, no auto-correction,
one logical step per line, and **no uncertainty markers** — it commits to a reading everywhere
and the student verifies) lives in `courses/_shared/transcription_prompt.txt`.

**The rendered verification surface — pick one (both optional):**

- **(a) A render-on-submit page.** One screen: photo left, pasted LLM source right, live KaTeX
  render with step numbers + "flag step N". Synchronous feedback (student fixes immediately);
  can also *be* the submission surface (store file + university-ID), replacing Google Forms.
  The render itself is a static client-side page (marked + KaTeX) — **low-risk**; malformed
  math shows an inline KaTeX error, which is useful signal, not a silent failure. The
  *storage/identity* half is the standard integration risk, and decouples from the render.
- **(b) A daily morning batch job.** Submission stays simple (Google Forms + Drive). A job runs
  each morning over yesterday's submissions, renders each, detects issues (KaTeX errors, empty,
  garbled), and emails the student "OK" or "re-upload needed." Reuses the existing nightly-job +
  reminder-email infrastructure; async feedback with a re-upload cycle, but the simplest intake.

Trade-off: (a) = best UX, more front-end + must be reliable live; (b) = simplest intake, reuses
batch/email infra, slower loop. Either satisfies the accountability requirement.

### 4.4 Storage and roster

| Thing | Today | Needs |
|---|---|---|
| Result blobs | `results/{assignment}/{github}.json` | course prefix |
| Submissions bucket | `GCS_SUBMISSIONS_BUCKET` | per-course bucket or prefix |
| Classroom roster | one CSV, loaded at startup | per-course roster |
| ID mapping | `ID_MAPPING_GCS_PATH` | per-course — see §4.4a; a Forms course may need none at all |
| Accommodations list | one list | per-course (or university-wide — **confirm**) |

### 4.4a The ID map — **DECIDED: Linear Algebra uses none**

The map exists to solve a GitHub-shaped problem: a repo gives a `github_username` and nothing else,
so a roster is the only bridge to a real name. A Form has no such gap — add a **full name** field
and the name arrives in the response row, with verified email collection anchoring identity to a
university account. Linear Algebra therefore keeps no roster.

Two standing actions regardless:

- **Never leave `ID_MAPPING_GCS_PATH` on its default** (`private/id_mapping.csv` = the OS roster).
  A course service on the default loads ~296 OS students' IDs and Hebrew names into a deployment
  with no reason to hold them, and exposes them to that course's admin console.
- **Delete a course's roster blob when the course ends** — the OS one once the late students finish.

**Built (2026-08-06).** `FORM_SOURCES[...]["name_column"]` names the form's name field;
`forms_stub.name_for()` reads it, `submission_source.student_name()` routes it (None on the GitHub
path, where a repo carries no name), and `run_grader_background` uses it **only to fill a gap** —
a roster, where one exists, stays authoritative. Status becomes `ok_name_from_form`. Unset the
column and it is a silent no-op, so nothing changes for Operating Systems.

⚠ **The form must actually have the field, and `name_column` must match its exact header.** With
no roster this is the sole source of the student's name; get it wrong and every grade email goes
out nameless.

### 4.4b Outbound email is per course — sender and template both

Two separate things, both currently Operating-Systems-shaped, both needed before any course
emails a real student.

**1. The sending account.** `SMTP_USER` / `SMTP_PASSWORD` / `TA_EMAIL` are per deployment.
`ai-exam-backend-la` has **none of them**, so grade emails cannot send and distress alerts have
nowhere to go. Each course should send from its **own staff address**, not the OS one: students
reply to it, and the reply must reach that course's team. Ask the course for the address and an
app password before the first real exam.

**2. The template.** `grade_email_template.py` is hardcoded for Operating Systems — the signature
("צוות הקורס — מערכות הפעלה"), the label "איכות הקוד", the `POST_SURVEY_URL`, and the +10
`ADAPTATION_BONUS_POINTS`, which is a course *policy* rather than a system feature. None of it is
course-scoped yet. A maths course needs "איכות הפתרון הכתוב", its own signature, its own survey
link (or none), and its own bonus decision.

The natural shape is the one `config.COURSE_UI` already uses — a per-course dict keyed by
`COURSE_ID`, with the template pulling its strings from it. Draft for staff review:
`docs/FOR_LA_STAFF_grade_email.md`, which lists the six decisions that must come back before this
can be wired.

### 4.5 Environment variables

Already course-dependent, must be set per course:

`ASSIGNMENT_NAME` · `GITHUB_ORG` · `GITHUB_REPO_PATTERN` · `GITHUB_APP_ID` ·
`GITHUB_INSTALLATION_ID` · `GITHUB_PRIVATE_KEY[_PATH]` · `GITHUB_BRANCH` ·
`GITHUB_FILES_PATH` · `GCS_SUBMISSIONS_BUCKET` · `ID_MAPPING_GCS_PATH` ·
`EXAM_DURATION_SECONDS` · `TA_EMAIL` · `VIEWER_PASSWORD`

New: **`COURSE_ID`**.

Plausibly shared: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `SMTP_*`, DB credentials.

> **If — and only if — a course uses GitHub**, it needs its own GitHub App installation on
> its own org, which has external lead time. For a non-GitHub course this whole env block is
> replaced by whatever the chosen intake adapter needs (§4.3c). **Confirm the intake
> mechanism per course before provisioning anything.**

### 4.6 Surfaces that assume one course

- **Admin console** — every view aggregates across all assignments; needs a course filter or a per-course deployment.
- **Grade emails** — templates name the course; the survey link is course-specific.
- **Calendar integration** — one calendar today; two courses need separate slot calendars.
- **Cron jobs** — the daily grade-email and reminder jobs iterate all assignments.

---

### 4.7 Backups and disaster recovery — audited 2026-07-20

Audit of `ai-exam-db` (POSTGRES_15, db-f1-micro, ZONAL, me-west1, created 2026-04-20).

**Retention is sane — we are not hoarding backups.**

| Setting | Value |
|---|---|
| Automated backups | enabled, daily at 00:00 UTC |
| Retention | **7, by COUNT** — the 8th backup deletes the 1st |
| Point-in-time recovery | enabled, 7 days of transaction logs |
| Backups actually present | exactly 7, all `AUTOMATED`, none `ON_DEMAND` |
| Backup location | `eu` (multi-region), instance is in me-west1 |

The absence of `ON_DEMAND` backups matters: **on-demand backups ignore the retention policy
and persist until manually deleted.** That is the usual way these bills grow without anyone
noticing. We have none. If anyone takes a manual backup before a risky migration, it must be
deleted afterwards or it stays forever.

**Cost is negligible.** Database is **197 MB**. Official me-west1 SKU pricing:

| Item | Rate | Monthly |
|---|---|---|
| Backups (SKU "Cloud SQL: Backups in Israel") | $0.088 / GiB-month | **~$0.03–0.12** |
| Instance (Zonal Micro) | $0.0116 / hour | ~$8.47 |
| Storage (Zonal Standard, 10 GiB provisioned) | $0.187 / GiB-month | ~$1.87 |

Backup range reflects incremental (~0.3 GiB) vs. worst-case 7 independent full copies
(1.35 GiB). PITR transaction logs bill under the same backup SKU and are negligible on a
near-idle database. **Backups are ~1% of the Cloud SQL bill. There is nothing to optimise
here — do not spend time on it.**

Side note: 10 GiB is provisioned against 197 MB used, costing ~$1.87/month for storage we do
not need. Cloud SQL disks cannot be shrunk, so this is sunk unless the instance is rebuilt.

**Deletion protection: enabled 2026-07-20.** ✅

Automated backups live *inside the instance* — delete the instance and every backup goes with
it. Retention length is no defence against that, so `deletionProtectionEnabled` was turned on
(`gcloud sql instances patch ai-exam-db --deletion-protection`; verified `true`, instance
still `RUNNABLE`, backup config unchanged). Deleting the instance now requires explicitly
clearing the flag first.

Still open, both optional:

- **Off-instance export.** A periodic `gcloud sql export sql` to GCS produces an object that
  survives instance deletion. At 197 MB it costs cents. Not done — the result blobs in GCS
  already cover most of what we would want to recover.
- **Project lien**, which would additionally block project deletion. Not set.

**Retention window: 7 days is a deliberate choice, not an oversight.** It covers problems
found within the week, which is the realistic case for data corruption or a bad write. It
does *not* cover anything surfacing later — grading disputes, for instance, appear weeks
after the fact — but exam result blobs live in GCS and are unaffected, so the exposure is
limited to session-level database state.

**Multi-course impact:** under Option A (§3), each course gets its own instance, so every one
of the above settings must be configured per instance — deletion protection and exports
included. Under Option B there is a single instance and a single backup configuration, but a
restore affects every course at once, so a per-course accident forces a global rollback
decision. Neither is clearly better; it should be a conscious part of the §3 decision.

---

### 4.7b Per-question scoring ceiling (`excellent_answer`) — prompt-only, DONE in skeletons

A new `excellent_answer` field per pool question, describing what a top 5/5 answer
demonstrates and what separates a 5 from an adequate 3. Motivation: in a-3, q02 was asked of
40 students and **none ever scored 5** — the question had an invisible ceiling. This anchors
the top of the scale so full understanding is scored as such.

**No backend change required — the architecture already supports it:**

- The examiner is fed topics only through `QuestionPicker.format_topic_for_examiner()`
  (`plan_assembler.py`), a 5-field whitelist (files/focus/dimension/difficulty/examiner_notes).
  A new pool field is **not** in that whitelist, so the examiner never sees it — it cannot
  leak into question phrasing.
- The grader receives the entire transcript serialized (`agents.py` `call_grader`), and the
  transcript stores the raw `chosen_topic` (all 9+ pool fields). So `excellent_answer` reaches
  the grader automatically.

Done in the skeletons: generated in `pool_step1`/`pool_step2`, consumed in `grader`, with a
graceful fallback for older pools that lack it. **Takes effect only for pools regenerated
next year** — existing pools have no `excellent_answer`, and the grader falls back to its
built-in anchors for them.

Verify once, when the first next-year pool is live: that `chosen_topic` in a real transcript
still carries the full raw question (it did in every 2026 a-3 blob) so the field actually
reaches the grader.

### 4.8 Admin: question-pool item-analysis panel — ✅ BUILT (offline compute + read-only endpoint)

**Design chosen (2026-07):** offline compute → GCS blob → read-only endpoint, per assignment,
manual recompute. Keeps `sentence-transformers` out of the backend image entirely.

**Where it lives:**
- `backend/scripts/item_analysis.py` — the offline computer. Reads blobs (local dir or GCS) +
  the pool JSON; prints a per-question table; `--json out.json` dumps the report;
  **`--write-gcs`** uploads it to `gs://{GCS_SUBMISSIONS_BUCKET}/item_analysis/{assignment}.json`
  (path constant `ITEM_ANALYSIS_GCS_PATH` in `config.py`). This is the "recompute".
- `GET /api/admin/results/item-analysis?assignment=X` in `main.py` — **read-only**; returns the
  stored blob, or `{computed: false, hint: "..."}` if never run. No compute in the request path,
  so no heavy dependency and no per-request cost.

**Recompute runs nightly at 23:00 Asia/Jerusalem — a separate Cloud Run JOB (decided 2026-07),
not the exam backend.** This keeps `sentence-transformers`/torch out of the serving image.

- Entrypoint: `scripts/item_analysis.py --all --write-gcs` (loops `config.KNOWN_ASSIGNMENTS`,
  model loads once, writes one report blob per assignment).
- Image: `backend/Dockerfile.itemanalysis` (backend + CPU torch + sentence-transformers, with
  the embedding model pre-baked so cold-starts don't download it). Built/deployed by
  `cloudbuild-itemanalysis.yaml` → Cloud Run Job `item-analysis-nightly` (me-west1, 2Gi/2cpu,
  service account = the backend's, `GCS_SUBMISSIONS_BUCKET=ai-exam-submission`).
- Trigger: Cloud Scheduler at `0 23 * * *` Asia/Jerusalem → `run.googleapis.com` job-run.

**Deploy (one-time):**
```
# build image + create/update the job
gcloud builds submit --config cloudbuild-itemanalysis.yaml
# nightly trigger (once)
gcloud scheduler jobs create http item-analysis-nightly-trigger \
  --location=me-west1 --schedule="0 23 * * *" --time-zone="Asia/Jerusalem" \
  --uri="https://me-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/ai-examiner-system/jobs/item-analysis-nightly:run" \
  --http-method=POST \
  --oauth-service-account-email=1023741330092-compute@developer.gserviceaccount.com
# smoke-test now (also populates the blobs so the panel has data):
gcloud run jobs execute item-analysis-nightly --region=me-west1
```
The compute SA needs `roles/run.invoker` to be triggered by Scheduler (grant if the create
call reports permission denied). Manual recompute is still possible any time by re-running
`gcloud run jobs execute` or the script locally.

Report carries `computed_at` and `divergence_available`. Verified against a-3: reproduces every
scratchpad number.

> **Possible future upgrade — incremental divergence (§4.8i):** keep divergence always-fresh via
> a running per-question embedding sum at exam finish, at the cost of putting the embedding model
> in the backend. Not needed while the nightly job exists.

Verified against a-3: reproduces every scratchpad number (residuals, divergence bands,
discrimination, take rates) and the recommendations below. Calibrated thresholds baked in
(`DIV_GREEN=0.78`, `DIV_YELLOW=0.84`).

Original spec below.

### 4.8x Admin: question-pool item-analysis panel (design)

An offline-computed, stored-then-read panel scoring every pool question after an assignment
closes (same pattern as the `result_summary` table — no per-page-load cost). Per question,
compute from the stored blobs:

- **take rate** = asked / offered. Near-zero means the examiner keeps rejecting it (a-3: q19
  offered 165×, chosen 1×).
- **residual difficulty** = mean(score − that student's own mean score). Corrects for the
  fact that adaptive routing sends strong students to hard items. Compare to the label to
  catch mislabels (a-3: q12 labelled `hard` but easier than the average `medium`).
- **ceiling/floor** = % scoring 5 / % scoring ≤2. No 5s means no headroom (a-3: q02, 40
  asked, 0 fives).
- **semantic divergence** = does one pool entry produce genuinely different questions per
  student. Method below.

Emit plain-language recommendations: "move q12 hard→medium", "remove q19 — never selected",
"q02 has no headroom", "q08 template-like — replace".

**Divergence metric (the novel part).** Mean pairwise cosine of a question's instantiation
embeddings, computed with a ~120 MB multilingual sentence-transformer
(`paraphrase-multilingual-MiniLM-L12-v2`) — **no LLM call, no per-exam cost**, run offline.

- Per pool-entry, over its own instantiations only. Use the exact O(n) identity
  `mean_pairwise = (n·‖centroid‖² − 1)/(n−1)` for L2-normalized embeddings — no sampling,
  no O(n²).
- Needs ≥ ~8 instantiations, so it is post-hoc (report on a pool after a run, not before).
- Band it. **Calibrated across a-1 + a-2 + a-3 (50 questions, n≥8): 🟢 <0.78 / 🟡 0.78–0.84 /
  🔴 >0.84** (tertiles of the combined distribution; min 0.58, median 0.82, max 0.95).
  ⚠️ Assignments skew: a-1 median 0.76, a-3 0.79, but **a-2 0.85** — a-2's questions are
  systematically more template-like, so an absolute threshold flags most of a-2. Show the
  admin the raw score AND the within-assignment rank, and treat the band as a review flag,
  not an automatic verdict.
- **Do NOT use a lexical proxy** (mask identifiers + string similarity): tested, it *inverts*
  the ground truth, because it measures phrasing variety not meaning.

Genuinely novel capability, not just ops tooling: per question the admin sees both whether
the examiner favours it (take rate) and whether it actually adapts per student (divergence).
The three signals converged on the same weak a-3 items, which is encouraging. Reference
implementations exist as scratchpad scripts (`divergence_panel.py`, `a3_irt.py`).

---

### 4.8i Incremental divergence — update per exam, exact, no re-embedding (design)

The divergence metric is a **mergeable statistic**: it depends only on the count and the
*sum* of a question's instantiation embeddings, so it can be maintained incrementally with an
O(1) update per exam and gives results **identical** to the batch computation (not an
approximation).

**Derivation.** For a question's `n` L2-normalized instantiation embeddings `v₁…vₙ`, let the
running sum be `S = Σ vᵢ` and the centroid `c = S/n`. The metric is mean pairwise cosine:

```
divergence = (n·‖c‖² − 1)/(n − 1)      and   n·‖c‖² = n·‖S/n‖² = ‖S‖²/n
           = (‖S‖²/n − 1)/(n − 1)
```

So the **only state per question is `(n, S)`** — an integer and one 384-float vector (~1.5 KB
for the MiniLM model). On each exam finish: embed the 2–3 questions that were asked (~50 ms on
CPU), do `S[qid] += v; n[qid] += 1`. Divergence for any question is then O(dim) on demand. No
storing past embeddings, no pairwise, no recompute — because divergence reduces to a function
of a running sum, it composes exactly like a mean does from its sufficient statistics.

**The one real cost / the decision:** embedding the finished exam's questions needs the
sentence-transformer model **in the backend** (~120 MB image + resident RAM, lazy-loadable;
the backend is already 3 Gi). That **reverses the §4.8 "keep the image lean, compute offline"
decision** — it is the whole tradeoff. In exchange, divergence is always current with zero
manual recompute and zero per-request cost.

**If adopted:** store `(n, S)` per question in a small GCS blob or a `question_embed_state`
table, updated at exam finish behind a flag (same pattern as `RESULT_SUMMARY_ENABLED`). The
other three metrics (take rate, residual, ceiling) are cheap aggregations over
`result_summary` and can be computed on demand, so with this in place the whole item-analysis
panel becomes real-time and the manual `--write-gcs` recompute (§4.8) is no longer needed for
divergence. Note the ≥8-instantiation floor still applies before a divergence value is
meaningful.

---

### 4.9 Second code-reviewer validator (hallucination guard) — ✅ BUILT, flag-gated off

**Where it lives**
- Prompt skeleton: `courses/_shared/reviewer_validator_skeleton.txt` (renders per course).
- Live prompt read by the backend: `backend/prompts/reviewer_validator_prompt.txt` (the
  rendered OS version; a new *inert* file — the live examiner/grader/reviewer prompts were
  NOT touched). Path constant `REVIEWER_VALIDATOR_PROMPT_PATH` in `config.py`.
- Agent: `ReviewerValidatorOutput` schema + `call_reviewer_validator()` in `agents.py`.
- Wiring: a gated block in `run_grader_background` (`main.py`, "Phase 1b"), between the code
  reviewer and the grader.

**Enable it:** set `REVIEWER_VALIDATOR_ENABLED=true`. Gated additionally on
`staticCodeQualityScore < 100` (a perfect score has nothing to challenge). Runs on the
primary model (Opus 4.8 — it's a correctness guard, not a place to save tokens).

**It corrects the grade (decided 2026-07, was originally flag-only).** When it finds unfair
deductions it returns `corrected_static_score` (≥ the reviewer's score — it can only RESTORE
points, never lower) and a minimally-edited `corrected_student_feedback`. `run_grader_background`
applies both: the corrected static score flows into `compute_final_grade`, and the originals
are kept as `originalStaticCodeQualityScore` / `originalStudentStaticFeedback` for audit. The
full verdict rides in the blob under `code_review.reviewerValidation`, and
`result_summary.reviewer_challenged` flags it for the admin panel. Errors are swallowed —
a validator failure leaves the original review untouched and never fails a grade.

**Skeleton input is NOT available (§4.3d), so it is not passed.** The provided/starter files
are not stored anywhere the backend can load — e.g. `common.h`, which defines the `void`
`write_all`, is not in any `_files.json` and is never fetched, which is *why* the reviewer
hallucinated the deduction. Passing the real skeleton needs those files gathered and stored
per assignment first (see §4.3d / the checklist below). Until then the validator compensates
with a heuristic in its prompt: **if the reviewer penalized the use of a function/helper whose
definition is not in the submitted files, it is almost certainly provided → challenge it.**
This recovers the `write_all` case (call present, definition absent) without the skeleton; the
`volatile` case is already covered because the validator sees the README.

Original design notes below (cost, rationale) are unchanged.

**Goal.** Guard against the reviewer deducting for things it should not have — the 2026

**Goal.** Guard against the reviewer deducting for things it should not have — the 2026
`write_all`/`volatile` failure mode. The skeleton fixes (skeleton-as-input §4.3d, the
do-not-penalize list) reduce this at the source; a validator is defense-in-depth on top.

**Shape (asymmetric — checks over-penalization only, as requested).** After the code reviewer
returns, a second agent sees: the assignment README + skeleton, the student's submission, and
the first reviewer's `codeReviewNotes` (the deductions). It answers one question per
deduction: *is this a fair deduction, or did the reviewer penalize provided/spec-mandated/
not-required material?* Output: a list of challenged deductions + a suggested score
correction, OR (safer) just a flag for human review that never auto-changes the grade. It
does **not** re-review for missed problems — that is deliberate, and halves the work.

**Cost (≈230 submissions).** Input ≈ 10K tokens/student (README+skeleton ~7K cacheable +
code ~2.5K + notes ~0.5K), output ~0.5K.

| Model | Per run | With prompt caching + gate |
|---|---|---|
| Opus 4.8 | ~$14 | ~$6 |
| **Haiku 4.5** | ~$2.90 | **~$1** |

Two multipliers: (1) it is a *checking* task, so **Haiku is appropriate** — 5× cheaper than
Opus; (2) **gate it on `staticCodeQualityScore < 100`** — a perfect score has no deduction to
challenge, skipping ~half the cohort. Net **~$1/run on Haiku**, negligible. Batch API halves
it again if not latency-sensitive (grading is async, so it isn't).

**Recommendation.** Build it as Haiku, gated on score<100, flag-only (no auto-grade-change) —
the flag lands in the admin panel next to the student. Revisit auto-correction after a term of
seeing how often it fires and how often it is right. The appeal outcomes from 2026 are a ready
labeled eval set (we *know* the write_all/volatile deductions were wrong).

### 4.10 Admin endpoint → Postgres `result_summary` (latency + cost) — ✅ BUILT, flag-gated off

**Where it lives**
- Table: `ResultSummary` in `models.py` (auto-created on startup by `create_all` — no manual
  migration). One row per (assignment_name, github_username).
- The single funnel: `backend/result_summary.py` — `summary_from_blob()` (pure transform)
  and `upsert_summary()` (Postgres `ON CONFLICT`, SQLite `merge` fallback). **Every grade
  write must go through this.**
- Backfill / rebuild: `backend/scripts/backfill_result_summary.py` (reads blobs — the truth —
  and upserts; `--dry-run`, `--local-dir`, `--sqlite` for offline testing).
- Fast read endpoint: `GET /api/admin/results/aggregate_fast` in `main.py` — same response
  shape as `/aggregate`, reads only the table. Returns `{"empty_table": true}` if not
  backfilled so a caller can fall back to the blob-backed `/aggregate` (which is untouched).
- Sync hook: gated block in `run_grader_background` ("keep the result_summary read-model in
  sync"), behind `RESULT_SUMMARY_ENABLED`.

**Enable it:** (1) `python scripts/backfill_result_summary.py` once to populate from existing
blobs; (2) set `RESULT_SUMMARY_ENABLED=true` so new grades keep it fresh; (3) point the admin
frontend at `/aggregate_fast`. Verified against a-3: SQL aggregation reproduces the dashboard
(final mean 85.6 vs 85.4, histogram exact) from ~550 tiny rows instead of a 35 MB blob scan.

**Validated offline**, not yet run against the live DB. Original design notes below.

**The problem, measured.** `_load_assignment_blobs()` (`main.py`) downloads **every**

**The problem, measured.** `_load_assignment_blobs()` (`main.py:2312`) downloads **every**
result blob from GCS on an admin aggregate load — a-3 is 211 blobs / ~35 MB — strips the
heavy fields in Python, and aggregates in a loop. It is cached in memory, and loading blobs
whole previously **OOM'd instances** (hence the 3Gi backend and the field-stripping). Every
cache miss re-downloads 35 MB and re-aggregates.

**The fix.** A `result_summary` Postgres table, one row per (assignment, github_username),
holding only the ~15 fields the admin actually reads:

```
result_summary(
  assignment_id text, github_username text,      -- PK (assignment_id, github_username)
  student_id text, hebrew_name text,
  final_grade int, oral_score int, static_score int,
  authorship text, integrity_flag bool,
  id_resolution_status text, status text,
  duration_min real, exam_date timestamptz,
  updated_at timestamptz
)
```

Admin aggregate = one SQL query (`AVG`, `COUNT`, `GROUP BY`, histogram via `width_bucket`) —
sub-50 ms, ~0 memory, no 35 MB download. The full per-student blob is still fetched from GCS
only when someone opens one student (already a single-blob read). This is also where the
§4.8 divergence/item-analysis numbers get stored and read.

**The one hard rule — every grade write funnels through ONE function.** There are three write
paths: initial grading, `/api/admin/regrade`, and **appeal edits**. Appeals currently edit the
GCS blob only, so the moment a summary table exists it is stale for every appellant unless
appeals write through the same function. This is the single thing that makes or breaks the
design; it must be enforced, not remembered.

**Migration.** One-off backfill from existing blobs → table, then keep in sync on every write.
Cost is negligible (550 rows × ~15 cols). Under Option B this table naturally carries a
`course_id`; under Option A it is per-DB. Either way it also unlocks cross-assignment stats
the current blob-scan cannot do cheaply.

**This is safe to build now** — it is additive (blobs remain the source of truth; the table is
a derived read-model) and touches admin/grading write paths, not the student exam flow.

### 4.11 Billing-account move + provisioning two new courses (2027 sem-1)

**Facts (checked 2026-07-20).** Project `ai-examiner-system` is **standalone** (no
organization parent), linked to billing account `0173AE-DE6ABA-CE9517`. OS runs in *second*
semester; the two new courses run in *first* semester, so **OS is not concurrent with them** —
which removes most of the cross-course-isolation pressure for the first run.

**Moving to the department's billing account — easy, no data moves.** A project's billing
account is a link, changed in place:

```
gcloud billing projects link ai-examiner-system --billing-account=<DEPT_ACCOUNT_ID>
```

Requires `billing.resourceAssociations.create` on the dept account (they grant us **Billing
Account User**) + `resourcemanager.projects.setBillingAccount` on the project (we have it).
**No redeploy, no downtime, no data migration** — only who-pays changes.

> Two caveats: (1) the **BigQuery billing export resets** on an account change — historical
> cost data stays under the old account's export, new data flows to the new one; re-link the
> export after the move (Console-only, § existing billing notes). (2) If the department wants
> the project inside *their GCP org* (not just their billing), that is a separate
> project-migration-into-org operation, heavier than a billing relink — confirm which they
> actually want.

**Two new courses — recommend one project + DB + deployment each (Option A).** Reasons align
with §3 and are stronger here: the courses are brand-new (no existing data to migrate), OS is
not running alongside them (no shared-cohort argument), and student PII isolation is cleanest
with hard separation. Each course = a clone of the current stack: its own project (or at least
its own DB + Cloud Run services + GCS prefix + GitHub App + billing link to the dept account).

**Per-course provisioning checklist (to be turned into a script):** create project → link dept
billing → Cloud SQL instance (+ deletion protection, §4.7) → GCS bucket → GitHub App install on
the course org → secrets (`ANTHROPIC_API_KEY` etc., can be shared or per-course) → deploy
backend + 3 frontend variants with the course's `COURSE_ID` and env → render + ship the
course's prompts (§4.1) → smoke-test the student lookup + one exam.

**Open decision for §3, now narrower:** with only two non-overlapping courses, Option A is
low-cost and low-risk; revisit Option B (single project, `course_id`) only if a third course
or a cross-course analytics need appears. The physical-exam-room constraint (§3) still gates
scheduling regardless of the software choice.

---

## 5. Suggested staging

**Buildable now, independent of the §3 decision** (additive, no student-flow impact):
- `result_summary` table + write-funnel (§4.10) — biggest admin latency/cost win.
- Item-analysis / divergence panel (§4.8) reading from that table.
- Second code-reviewer validator (§4.9), Haiku + gated.

> **Correction (2026-08-03):** §3 blocks *less* than this list implies. The identity rework
> (§4.3c), the intake adapter, the render/verify surface and all prompt/pool work are identical
> under Option A and Option B — only provisioning (§4.11) and the admin/entry surfaces depend on
> the answer. Linear Algebra work can start now; see `docs/LINEAR_ALGEBRA_PLAN.md` §0.

**Blocked on §3 / the department:**
1. **Decide Option A vs B** (§3). Blocks the deployment topology.
2. Namespace assignment IDs (§4.2) — do this even before a second course exists.
3. Wire prompts to `courses/<id>/rendered/` (§4.1) and add `--check` to the build.
4. Billing relink + per-course provisioning (§4.11) once the dept account is available.
5. Stand up a new course as a **parallel deployment with one pilot assignment**, small scale.
6. Only then generalise the admin surface to be course-aware.

---

## 6. Open questions

- [ ] **Option A or B?** (§3) — *blocked on the department: is there a second exam room/machine?*
- [ ] **How does each new course deliver submissions?** (§4.3c) — ask them, let them propose
- [ ] **What is the course-neutral student identifier** once GitHub username stops working as the PK? (§4.3c)
- [ ] Questions-per-exam and time-per-question for each new course → if not 3 × 5 min, all three layers (grader prompt, examiner prompt, backend clamps) need changing together (§4.3b)
- [ ] Is the accommodations list university-wide or per-course?
- [ ] Who owns the admin surface for a course we do not run — do their TAs get access, and to what?
- [ ] Does a shared student identity across courses matter for the correlation study? (An argument for Option B.)
- [ ] Retention: whose data is it, and who deletes it at semester end?
- [x] ~~Turn on Cloud SQL deletion protection~~ — done 2026-07-20 (§4.7)
- [ ] Optional: periodic Cloud SQL export to GCS, and/or a project lien (§4.7)
- [ ] Does the department want only our **billing** moved to their account, or the **project into their GCP org**? (§4.11 — very different amounts of work)
- [ ] Second code-reviewer validator: flag-only, or allowed to auto-correct the score? (§4.9)

---

## 7. Notes to fold in

<!-- Shachar: add migration material here; I will integrate it into the sections above. -->
No need for the surveys before and after exam anymore - it was just for the pilot. remove any mention of it.

---

## 8. Vertex AI / model-backend migration — cost management

**Status: opus-5 bump done, Vertex cutover NOT started.** Separate track from
multi-course — motivation is GCP-native cost management. Google prices Claude on
Vertex independently as a partner, and usage bills under the same GCP project as
everything else (GCS, Cloud SQL), broken out by SKU in Cloud Billing/BigQuery, instead
of a separate Anthropic invoice.

### 8.1 What's already done (2026-08-12)

| | Status |
|---|---|
| `EXAMINER_MODEL` / `GRADER_MODEL` / `CODE_REVIEWER_MODEL` → `claude-opus-5` (`config.py`) | ✅ done |
| `ANTHROPIC_FALLBACK_MODEL` → `claude-sonnet-5`, kept **different** from the primary — its job in `call_agent()`'s 429/529 cascade is to retry on a genuinely different model; setting it to Opus 5 too would make that retry step pointless | ✅ done |
| Removed `temperature=` from the Anthropic call in `call_agent()` (`agents.py`) — **required, not cosmetic**: Opus 5 400s on `temperature` being present at all, Sonnet 5 400s on any non-default value, and every call site was sending one (examiner's randomized `0.2–0.4`, grader/reviewer's hardcoded `0.1`). Left in, the bump would have 400'd on every session's first question. `temperature` still flows to the Gemini fallback, which accepts it. | ✅ done |
| Side effect to watch: the examiner's per-session temperature was deliberately injecting question variety, and the grader/reviewer's was aiming for consistency. Neither does anything now — Opus 5 doesn't take a sampling knob. If variety/consistency regresses, the fix is prompt-level, not a parameter. | ⚠ watch |
| Vertex client swap, GCP setup | ❌ not started |

### 8.2 Vertex cutover — code footprint (small, once greenlit)

Every real Anthropic call funnels through `call_agent()` in `agents.py`, which
`call_examiner_q1`/`call_grader`/`call_code_reviewer`/`call_reviewer_validator` all
take a pre-built `client` into rather than constructing their own — so the cutover is
mostly client-construction call sites, not business logic.

| Change | Files | Notes |
|---|---|---|
| `Anthropic(...)` → `AnthropicVertex(project_id=..., region=...)` | `main.py` (`_get_anthropic_client()`), `scripts/regrade_appeal.py`, `scripts/grade_assignment_code_review.py`, `eval/eval_common.py`, 3 `courses/_poc/*.py` scripts | 7 one-line swaps |
| Model ID strings | none | `claude-opus-5`/`claude-sonnet-5` use the same bare ID on Vertex — no `@date` suffix |
| Auth | env config | drop `ANTHROPIC_API_KEY`; add GCP `project_id`+`region` (ADC). The GCS service account (`ai-examiner-system@...`) already in this repo can likely be reused — grant it `roles/aiplatform.user` |
| Dependency | `requirements.txt` | add the `[vertex]` extra |
| `agents.py` (tool schemas, forced `tool_choice`, prompt caching, 429/529 cascade) | none | same SDK, same `anthropic.APIStatusError` under either backend |

### 8.3 GCP logistics checklist (before cutover, not after)

- [ ] Reuse `ai-examiner-system` project (already billing-linked)
- [ ] Enable `aiplatform.googleapis.com`
- [ ] Enable `claude-opus-5` + `claude-sonnet-5` in Vertex Model Garden (per-model EULA)
- [ ] Grant `roles/aiplatform.user` to the calling service account
- [ ] Pick region — default `"global"` unless there's a residency reason to pin one
- [ ] **Request a Vertex quota increase before routing production traffic** — this is the step most likely to cause an outage if skipped, not the code
- [ ] Verify current Vertex pricing for `claude-opus-5`/`claude-sonnet-5` (Google prices Vertex-hosted Claude independently — don't assume parity with Anthropic's list price)
- [ ] Confirm/enable Cloud Billing export to BigQuery so Claude-on-Vertex spend is queryable by SKU, separate from Gemini and GCS in the same project

### 8.4 Open design item — emergency fallback to the native Anthropic API, with an email alert

**Decided:** keep the current native-Anthropic-API code path alive permanently as an
emergency cover once Vertex is primary — don't delete `ANTHROPIC_API_KEY` config or
the plain `Anthropic(...)` client construction. If Vertex fails/is unreachable, fall
through to it, and **email when that path fires** so it gets investigated rather than
silently running on the backup indefinitely. **Not yet designed or built.**

- Likely shape: one more rung on `call_agent()`'s existing cascade (`agents.py:335-363`)
  — Vertex primary, native API as a fallback attempt before Gemini — or a wrapper that
  catches a Vertex-specific failure and retries against the native client.
- Reuse existing email infra (`grade_email_template.py`, `distress_email_template.py`,
  `google_apis.py`-based sending) rather than adding a new mechanism.
- Needs a de-dup decision (email once per incident, not once per request, on a
  sustained Vertex outage) before it ships.

### 8.5 Feature parity / cost notes

Nothing used in production today (`agents.py`) is missing on Vertex — Messages API,
forced tool use, system prompts, and the manual per-block prompt caching at
`agents.py:343,413,680` are all fully supported. Not available on Vertex, unused today
but worth knowing if it comes up: Batches API (loses the 50% discount), Files API,
server-side code execution/web fetch, Managed Agents, fast mode. Vertex bills Claude
usage under `aiplatform.googleapis.com` by SKU, alongside the existing Gemini fallback
calls in the same project — isolate "Claude spend" by SKU/BigQuery query, not the
top-line Vertex AI total.