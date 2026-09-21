# Linear Algebra — implementation stages

> Decisions and rationale live in `MULTI_COURSE_MIGRATION.md`. This is only the sequence.
> Target: semester 1, starts ~late October 2026. Written 2026-08-03.

## Does any of this touch the live OS system?

**No, for everything through POC 3.** Explicitly:

- The Google Form + Drive folder live in a personal Google account, outside the GCP project.
- The POC ingest script must write to its own bucket or a `poc/` prefix — **never** the paths the
  OS backend reads (`results/…`, the submissions bucket) — and must not open the production DB.
- `courses/_poc/verify_render.html` is a local file with no network calls of its own.
- The TEST profile renders only to `courses/linear-algebra-TEST/rendered/`. The backend reads
  `backend/prompts/` via `config.py`, so a rendered TEST prompt cannot be picked up by accident.
- POC 3 runs as a local script against the TEST prompts. Do not point it at the deployed backend,
  and do not add a linear-algebra assignment to `config.py`.

**The stages that do touch live code are 4–7** (a nullable DB column, the frontend viewer, the
`codeLine`→`fileLine` rename). Schedule them once late OS students are finished. The rename fails
*silently* — highlighting just stops — so it goes in one commit with the backend accepting both
field names for a release.

## Done so far (2026-08-04)

**POC 1 — Google Forms intake: proven end to end.** Sheet → 9-digit ID → Drive file →
GCS, on a real form response. `backend/forms_stub.py` (Forms/Drive adapter),
`backend/submission_source.py` (per-assignment router), `config.FORM_SOURCES` (registry).
`main.py` now imports from the router, so GitHub and Forms run side by side — GitHub is
the default, so anything not in `FORM_SOURCES` is untouched. `drive.readonly` added to
`google_apis._SCOPES`; Drive API enabled on the project.

**POC 2 — transcription: six past solutions converted** (`past_examples/*/poc2_out/*.md`),
Opus 5 on `courses/_shared/transcription_prompt.txt`. 27 distortions across 526 steps
(~5%); the one clean scan transcribed with zero. Bake-off details below.

**`student_key` groundwork.** `config.student_key_for()` derives `gh:<user>` / `id:<digits>`
from `FORM_SOURCES`; `Session.student_key` is written on every new session alongside
`github_username`, which stays authoritative. **No read has been switched yet** — this is
inert for OS.

> The migration was run by hand in Cloud SQL Studio; the local script could not reach the
> instance (this network blocks egress to Cloud SQL, and will block any future migration
> run from here — use Studio or Cloud Shell). What was executed:
>
> ```sql
> ALTER TABLE sessions ADD COLUMN IF NOT EXISTS student_key VARCHAR;
> CREATE INDEX IF NOT EXISTS ix_sessions_student_key ON sessions (student_key);
> UPDATE sessions SET student_key = 'gh:' || github_username
>  WHERE github_username IS NOT NULL AND github_username <> ''
>    AND (student_key IS NULL OR student_key = '');
> ```
>
> ⚠️ A model carrying `Session.student_key` against a database without the column errors
> on **every** session read, including mid-exam. The migration must precede the deploy.

**Verifying a deploy did not change the live prompts.** Startup logs a fingerprint per
prompt (`[prompts]` lines) and every exam start carries the examiner hash. To compare
against your working copy, hash the text the way `_read_file` does — decoded and
**stripped** — not the raw bytes; otherwise CRLF line endings and trailing newlines
produce false mismatches:

```powershell
cd backend
python -c "import hashlib;[print(f, hashlib.sha256(open('prompts/'+f,encoding='utf-8').read().strip().encode()).hexdigest()[:12]) for f in ['examiner_prompt.txt','grader_prompt.txt','code_reviewer_prompt.txt']]"
```

Verified on the 2026-08-04 deploy: `COURSE_ID=''`, examiner `e0c174ced401`,
`source=github`, `student_key='gh:EinatNoyman'` — OS unchanged.

## Stages

| # | Stage | Blocked by |
|---|---|---|
| 0 | LA course profile + render (**TEST version done**: `courses/linear-algebra-TEST/`) | — |
| 1 | **POC 1 — Google Form + Drive intake** | — (your own Google account) |
| 2 | **POC 2 — transcription fidelity** | — |
| 3 | **POC 3 — mock exam, see the 3 questions** | 0 + 2 + a question pool |
| 4 | Identity: `student_key` + `IDENTITY_MODE` (9-digit ID instead of GitHub username) | — |
| 5 | Intake adapter (GitHub + Drive behind one interface) | 1, 4 |
| 6 | Math viewer in the exam frontend | 2 |
| 7 | Wire `courses/<id>/rendered/` prompts + `codeLine`→`fileLine` rename | OS off-season |
| 8 | Question pool for the first examined assignment | staff review |
| 9 | Provision + smoke + staff mock exams | §3 scoping decision |

§3 (deployment-per-course vs `course_id` column) blocks only stage 9.

### Folded in from `MULTI_COURSE_MIGRATION.md` (missed in the first pass)

| Where | Item |
|---|---|
| stage 4 | §4.2 namespace assignment IDs as `<course>/<assignment>` — and the retake lock keys on it, or LA `ex1` collides with OS `assignment-1` |
| stage 5 | §4.4 per-course storage: result-blob prefix, submissions bucket, roster, ID mapping, **accommodations list** |
| stage 7 | §4.3d also renames `bugPivotUsed`→`errorPivotUsed`; historical blobs keep the old key |
| stage 7 | §7 remove the pre/post-exam surveys entirely — they were pilot-only (`google_apis.py`, the post-survey link in the grade email, admin stats) |
| stage 8 | §4.7b LA pools are the first to carry `excellent_answer` — verify once on a real transcript that `chosen_topic` still reaches the grader with it |
| stage 9 | §4.3b pre-launch check: if the course ever moves off 3 questions, grader prompt + examiner prompt + the two `min(..., 3)` clamps must move together |
| stage 9 | §4.6 course-aware surfaces: admin views, grade-email wording, cron jobs that iterate all assignments, the nightly item-analysis job's assignment list |
| stage 9 | §4.7 per-instance backup settings + deletion protection if a second DB is created |
| skeletons | §4.3d(4) outstanding: raise the missing-deliverable penalty above today's 10–15 points in `submission_reviewer_skeleton.txt` (re-renders OS too — do it deliberately) |
| stage 7 | `config.py` pins `claude-opus-4-6` for all three agents; LA should launch on a current model. **Bumping is not a one-line change:** `agents.py:348` passes `temperature=` on every Anthropic call, which Opus 5 rejects with a 400 (keep it on the Gemini fallback path, which still accepts it), and `max_tokens=4096` needs raising because thinking is on by default and shares that budget |

## The three POCs

**POC 1 — Google Form intake.** Form collects the 9-digit university ID + one file per exercise.
Responses land in a Sheet, uploads in a Drive folder, a script pulls them into GCS. The ID field
is the point — it is the course-neutral student key the migration needs. Watch: uploads require
Google sign-in (breaks on personal Gmail), the folder and Sheet must be shared with the service
account, Drive API is not enabled on the project yet.
*Done when:* 5 test responses land keyed by ID, and a resubmission resolves to the latest.

### POC 2 bake-off — which transcriber (2026-08-03)

Six transcriptions of the same submission (`EX1SOL100.pdf`), all scored in **one call** against
**one** 128-step inventory of the original (`courses/_poc/poc2_bakeoff.py`, output
`poc2_out/bakeoff6.json`). BLOCKING = content dropped, invented, or uncertainty hidden.

| | Candidate | BLOCKING | tolerated |
|---|---|---|---|
| **A** | **Opus 5, strict one-paragraph prompt** | **0** | 5 |
| F | Sonnet 5, xhigh effort, relaxed prompt | 5 | 8 |
| D | Sonnet 5, low effort, relaxed prompt | 6 | 13 |
| C | GPT (course professor's own prompt) | 7 | 3 |
| E | Sonnet 5, high effort, relaxed prompt | 8 | 7 |
| B | Claude, dual `.md`+`.html` in one pass | 10 | 8 |

**Method note — scoring each candidate in its own call does not work.** Across five separate
runs the differ reported 82/96/96/112/118 steps for the same PDF, and the blocking count
correlated with that number at **+0.91** — it was measuring how thoroughly the differ read the
source that run, not the candidate. Always score candidates together, in one call.

**Transcription findings:**

1. **The strict prompt wins, and relaxing it causes fabrication.** A permissive variant
   ("completeness is the bar, not literal fidelity") produced invented matrix rows and
   reduction steps in every candidate that used it. Fabrication is categorically worse than
   the tolerated failures: a student can defend a step the LLM tidied, but not one it made up,
   and the reviewer would be grading mathematics that never existed. **Do not relax it.**
2. **No uncertainty markers.** An earlier variant that required them produced 262 markers on a
   single submission, almost all on ordinary Hebrew words rather than on the mathematics. The
   prompt now commits to a reading everywhere and the student is the correction mechanism —
   they check the output against their own page before submitting.

   Markers are not merely noisy, they are actively harmful downstream: in the 2026-08-05 pilot
   exam the examiner read them as evidence, picking a question because *"the transcription has
   many [?] marks suggesting uncertain steps"*. That is a property of the transcriber, not of
   the student. Do not reintroduce them without re-measuring, and note that **naming** the
   syntax anywhere a model can see it is enough to get it emitted — which is why neither the
   student-facing prompt nor the course profile mentions any marker syntax.
3. **Asking one pass for two output formats costs accuracy.** Candidate B (`.md` + `.html`
   together) is last. The two artifacts also disagreed with each other on 29 math expressions,
   dropped every row-operation label, and lost half the uncertainty markers that variant emitted.
3. **A rendered PDF cannot be the submitted artifact.** Text extraction from the professor's
   PDF yields 7,749 characters fragmented across 1,466 lines with **zero** `$` delimiters —
   the LaTeX source is gone, so it cannot be line-anchored, re-rendered, or verified.
4. **Sonnet is not the cheap option here.** At `xhigh` it took 876s and ~91k output tokens
   (~$1/submission) against Opus at 142s and ~12k (~$0.31), and still fabricated. Note the
   Sonnet runs used the relaxed prompt, so a strict re-run is the fair comparison.
5. Sonnet at default effort with `max_tokens=32000` returned **zero bytes** — thinking and
   output share the budget. Anything on Sonnet needs a large budget or reduced effort.

**POC 2 — transcription fidelity. ✅ RUN on ex1 (2026-08-03) — result below.**
`courses/_poc/poc2.py transcribe` sends each PDF with `courses/_shared/transcription_prompt.txt`,
then a second adversarial call that compares the transcription against the original and lists
every difference. Output in `courses/linear-algebra/past_examples/ex1/poc2_out/`.

| Submission | Source | Result |
|---|---|---|
| EX1SOL70 | small/clean PDF | **faithful** — reproduced the student's own errors unchanged |
| EX1SOL100 | 3.2 MB scan | **not faithful** — 7 semantic changes, 2 dropped, **1 silent correction** |
| EX1SOL90 | 0.7 MB scan | **not faithful** — 7 semantic changes, 2 dropped, **1 silent correction**, most Hebrew prose replaced by `[ILLEGIBLE]` |

The silent corrections are exactly the disqualifying failure: `s,t ∈ ℝ` → `ℂ` (repairing the
student's wrong field) and `y=3` → `x=3` (normalising a slip). The semantic changes are mostly
sign flips and coefficient changes in matrices. The differ's evidence is checkable rather than
vague — e.g. "(0 7 8) would give 8+4·5=28≡6, breaking the very next step the student wrote".

**Two consequences, both design changes:**

1. **A single transcription pass is not safe on scanned handwriting.** The adversarial
   comparison pass moves from contingency to a **required pipeline step**. It works — it caught
   every one of these with a verifiable argument — and at roughly $0.15 per submission it is
   affordable at cohort scale.
2. **Intake must collect the photos as well as the `.md`.** Without the original image there is
   nothing to check the transcription against, and nothing to resolve a "that isn't what I wrote"
   dispute with. This is a POC 1 change: the Form needs a photo-upload field alongside the source.

Neither of these breaks the approach — the clean PDF transcribed faithfully, and the failures are
detectable rather than silent. But "student transcribes, we trust it" is not viable as stated.
*Still needed:* your read of two or three of the flagged diffs (`poc2_out/CHECK_THESE.md`), to
confirm the differ is right about what the handwriting says.

### The reviewer experiment — and the architecture change it forces

Ran the LA-TEST submission reviewer twice over the same three graded solutions: once on the
original PDFs, once on the transcriptions. **No reference solution supplied in either run.**

| Submission | Real | Reviewer on **PDF** | Reviewer on **transcription** | Transcription quality |
|---|---|---|---|---|
| EX1SOL100 | 100 | 96 | 88 | 7 semantic changes, 2 dropped |
| EX1SOL90 | 90 | 80 | **66** | worst — most Hebrew prose lost to `[ILLEGIBLE]` |
| EX1SOL70 | 70 | 60 | 62 | faithful |
| | | **MAE 8.0** | **MAE 14.7** | |

Rank order is preserved both ways, so **staff do not need to supply answer keys** — that is
settled, on evidence.

But the grade damage tracks the transcription damage almost exactly: the faithfully transcribed
submission is unchanged (60 → 62, noise), while the worst-transcribed one loses 14 points. The
reviewer reads dropped reasoning and `[ILLEGIBLE]` markers as missing work and marks down for
them — the student is penalised for their transcriber, not their mathematics.

**→ Decision: the submission reviewer should read the photo/PDF directly, not the transcription.**
Vision ranks the scans correctly on its own (MAE 8.0), so the transcription is needed only for the
examiner's line anchoring and the student's verification. That decoupling drops the blast radius
of a transcription error from *"wrong grade"* to *"the examiner points at a slightly wrong line"* —
which the student can push back on during the exam. It also means the static score never depends
on the weakest link in the pipeline.

*Caveat:* n=3, one run each, no repeats. The 2-point differences are noise; the 14-point drop with
a matching explanation is signal. Re-run with repeats before treating the exact numbers as firm.
Both runs are systematically harsh (mean signed error −8 on PDFs) — a calibration offset in the
TEST profile's scoring anchors, not a ranking failure.

**POC 3 — mock exam.** Sanity-check that the questions make sense before meeting the staff.
1. `python courses\render.py linear-algebra-TEST` (done).
2. Run `rendered/pool_step1_prompt.txt` with the exercise sheet (`ex1.pdf` or `ex4.pdf`) as the
   assignment instructions and "none" as the starter material; then `pool_step2_prompt.txt` to
   prune into the pool JSON.
3. Use a transcription from POC 2 as the student submission.
4. Run the examiner locally against that pool + submission and answer as the student.

*Done when:* you've read the 3 questions from a strong and a weak submission and they look like
questions about *that* solution rather than about linear algebra in general.

## Open with staff — Wednesday

Decisions they own:
1. **Submission route: Google Form now, or wait for our own page?** Form works in ~2 weeks,
   students verify on a separate page. Our page is one screen (paste → render → submit) but is
   frontend work that must hold up on deadline night. Recommend Form first — not exclusive.
2. **Source, not PDF** — students submit the Markdown their LLM produced. A PDF leaves the
   examiner nothing to point at. Show them the verify page.
3. Which assignments get examined (recommend 3 checkpoints, not every sheet).
4. Questions per exam — keep 3. Time per question is free to change; a proof may want 6–7 min.
5. Oral/submission weighting (we used 75/25).
6. Is the extended-time accommodations list per-course or university-wide?
7. Do their TAs get admin access, and to what?
8. Who owns the data at semester end and who deletes it?

What we need from them:
- The syllabus by week — **the one correction only they can make** is cutting the concept list in
  the profile down to what students actually know when each assignment is examined.
- Exercise sheets, roster with 9-digit IDs, extended-time ID list.
- A Google account to own the Form + Drive folder (a personal one works for the POC).
- Confirmation every student has a working BIU Google account.
- Cohort size and how many exam slots they can staff.
