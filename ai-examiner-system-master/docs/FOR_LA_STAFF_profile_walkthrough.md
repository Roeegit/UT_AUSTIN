# Filling in the course profile — Linear Algebra

**What this is.** One document that adapts the oral-exam system to your course. Everything
else — exam mechanics, fairness rules, scoring, how distress and hostility are handled — is
shared across all courses and you never touch it.

**What we need from you.** We have written a **draft profile from guesswork** and generated a
question pool from homework 1 with it. Your job is to correct the draft, not to write one.
The draft is wrong in places on purpose-of-necessity: we are not linear algebra teachers.

**Time.** About an hour for the profile, plus about half an hour reading the questions.

**Two files come with this note:**

- `COURSE_PROFILE.md` (linear algebra) — **the draft to correct.** Edit it directly.
- The Operating Systems profile — **reference only**, showing what a finished one looks like
  after a semeste of real use.

Values live between `<!-- BEGIN: X -->` / `<!-- END: X -->` markers. Only the text inside
those markers is used. Everything outside is notes, and you can ignore or rewrite it freely.

---

## The three that matter most

### 1. `DOMAIN_CONCEPTS` — the concepts your course is about

What we need from you here is: **check the list is right and complete for this
course** — remove anything that isn't yours, add anything missing, and correct the wording where
it isn't how you'd say it.

### 2. `DIMENSIONS` — the kinds of question that exist at all

These decide what gets generated. Ours are: `justification`, `case_completeness`,
`counterfactual_mutation`, `edge_case`, `method_choice`, `claim_direction`.

The test to apply to each: **would a student who does not understand their own solution
struggle with it?**

- Good: "which theorem licenses this step, and do its hypotheses hold here?", "if this matrix
  were singular, which line of your proof fails first?"
- Bad: "state the definition of a basis" — memorisable, searchable, and answerable by someone
  who merely read the solution.

Rename, merge, delete, add. Aim for 5–8. If one of ours is not a thing you would ever ask a
student in an oral, say so — that is useful information.

### 3. `DO_NOT_PENALIZE` — what must never cost marks

The automated reviewer will invent faults if it is not told your conventions. Ours currently
says: skipped routine algebra, notation variants (`Aᵀ` vs `A'`), Hebrew/English mixing,
informal justification of standard steps, a valid proof by a different route.

Be generous here — over-listing costs nothing, false deductions cost student goodwill and
create appeals. Add anything your students do that a strict reader might mark down but you
would not.

---

## The rest, briefly

| Block | What to do |
|---|---|
| `COURSE_NAME`, `EXAM_LANGUAGE` | Confirm. Currently "Linear Algebra (TEST)" and Hebrew. |
| `SUBMISSION_STRUCTURE` | Says one homework sheet is one file containing all its exercises, and that exercises are independent unless one says "using part (a)". Correct if wrong. |
| `DEMAND_SPECIFICS` | The Hebrew sentence the examiner appends to force the student to point at their own work. Ours: "בתשובתך, הפנה לשלב המדויק בפתרון שלך שבו עשית זאת." Rewrite in your own voice. |
| `QUALITY_CRITERIA` | What "good" means when scoring the submission itself: rigour, completeness of cases, correctness of the algebra. |
| `AUTHORSHIP_MARKERS` | **Leave as-is.** We have disabled it deliberately — every submission is machine-transcribed by design, so "looks machine-written" carries no information here and would flag everyone. |
| Exam policy table | Confirm or change: 3 questions, ~5 min each, 75% oral / 25% submission. The count of 3 is calibrated into the scoring and is a joint decision; the time per question is freely changeable and a proof may well want 6–7 minutes. |

---

## Separately: the question pool

We have generated 27 questions for homework 1. Reviewing them is a different job from the
profile and probably the more useful one.

For each question ask: **is it fair at this point in the semester**, is it about something the
exercise genuinely required, could a student answer it from the sheet alone without having done
the work, and is it answerable in about five minutes. Delete what fails — the pool is generated
larger than needed, so deleting is cheap and rewriting is not.

Also glance at each question's `excellent_answer`. It is read only by the grader and describes
what a top answer looks like. **It is your main lever on how strictly full marks are awarded** —
if the best possible answer to a question reads as merely adequate, cut the question.
