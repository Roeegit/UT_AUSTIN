# Course Profile — `<COURSE NAME>`

> **What this is.** The one document your course writes to adapt the oral-exam system to
> your field. Everything else — exam mechanics, fairness rules, scoring, how distress and
> hostility are handled — is shared across all courses and you do not need to touch it.
>
> **Who writes it.** The course lecturer or head TA. You know your course; we don't.
>
> **How long.** A few hours once, at the start of the course. Then it is fixed for the semester.
>
> **How to draft it.** See `PROFILE_META_PROMPT.md` — hand it to an LLM along with this
> form and the Operating Systems profile as a worked example. Then **calibrate**: generate
> questions for one past assignment, read 20 of them, and revise. Do not trust the first draft.

---

## 1. Course identity

| Field | Value |
|---|---|
| Course name (as students know it) | |
| Course ID / folder slug | |
| Language of the exam conversation | Hebrew / English |
| Primary language(s) students submit in | e.g. C, Python, MATLAB |
| What students submit | e.g. source files in a repo / notebooks |

Only text **between** the markers is read by the system. Everything else on this page is notes.

<!-- BEGIN: COURSE_NAME -->
<course name as students know it>
<!-- END: COURSE_NAME -->

<!-- BEGIN: EXAM_LANGUAGE -->
<Hebrew or English>
<!-- END: EXAM_LANGUAGE -->

---

## 2. What "concepts" means in your course

The generator anchors every question to a concept the assignment genuinely requires. In
Operating Systems those were "OS/systems concepts" — processes, syscalls, concurrency.

**In your course, a question should connect the student's code back to:**

> _(one or two sentences — the intellectual content the exam is meant to reach)_

**Concepts a student in this course is expected to command by mid-semester:**

> _(a short list — this is what stops the generator asking about material you teach later)_

If your examined assignments are spread across the semester, note that an early one can only
be asked about material taught by then — tell us and we can narrow the scope per assignment.

<!-- BEGIN: DOMAIN_CONCEPTS -->
<Both answers above, as prose: what the exam should reach, and the concepts students command.>
<!-- END: DOMAIN_CONCEPTS -->

---

## 2b. Submission structure

The question generator was written for a course whose submissions are source files
containing functions. It asks "what files must the student write, what functions go in
each, how do the files call each other" — questions that make no sense for a problem set of
independent exercises. **This block tells it what your course's work is actually made of.**

Answer four things:

1. **What is a deliverable?** (a source file? a proof? one numbered exercise? a notebook?)
2. **What is a component *within* a deliverable?** (a function? a proof step? a sub-part?)
3. **Do deliverables depend on each other, or are they independent?** Say so plainly — if
   your exercises are independent, the generator must be told, or it will invent
   connections that do not exist.
4. **One example of a well-formed `focus`** — a specific element of the work *in a specific
   context*, not a bare topic and not a location.

<!-- BEGIN: SUBMISSION_STRUCTURE -->
_(Replace this. Example for a proof-based course:_

_In this course a student's submission is a written solution set._
  _- A "deliverable" is one numbered exercise._
  _- A "component" is a single step of the argument — a lemma invoked, a case split, an
    algebraic manipulation._
  _- Exercises are INDEPENDENT of one another unless an exercise explicitly says
    "using the result of part (a)"._

_Example of a well-formed focus: "the case split at the point where the matrix is assumed
non-singular in exercise 3" — names the step AND its context. Contrast with "singular
matrices" (too bare) or "the third line of the proof" (a location)._)
<!-- END: SUBMISSION_STRUCTURE -->

### Starter material

What students are handed before they begin. A code course gives stubs and provided files the
student did not author, and a question must never ask them to defend one. A maths course
typically gives nothing but the exercise sheet. State it once here so nobody has to repeat it
each time a pool is generated. Keep the leading "2." — it is item 2 of the generator's inputs.

<!-- BEGIN: STARTER_MATERIAL -->
2. SKELETON / STARTER MATERIAL — <describe what students receive before starting, or state
   that there is none and that every line of the submission is therefore the student's own.>
<!-- END: STARTER_MATERIAL -->

### 2c. Grounding phrase

The examiner appends this to conceptual questions to force the answer to be grounded in the
student's own submission rather than answered from general theory. Write it in the exam
language, and make it name something concrete that only the author would know.

<!-- BEGIN: DEMAND_SPECIFICS -->
_(Replace this. Operating Systems uses: "בתשובתך, התייחס לשמות המשתנים שבקוד שלך."
— "In your answer, refer to the variable names in your code."
A proof-based course might instead ask the student to refer to the specific lemma or step
they used.)_
<!-- END: DEMAND_SPECIFICS -->

---

## 3. Question dimensions — **the most important section**

These categories dictate what kinds of questions get generated *at all*. They are also
used at exam time to phrase questions, so define them once, here.

**Operating Systems used:** `design_choice`, `edge_case`, `error_handling`, `api_depth`,
`code_flow`, `cross_file`, `counterfactual_mutation`.

Yours will differ. Aim for **5–8** dimensions.

| Dimension name (snake_case) | What it probes | Example phrasing in your field |
|---|---|---|
| | | |
| | | |
| | | |
| | | |
| | | |

### Choosing well — please read before filling the table

The system measures whether a student **understands** what they submitted. It is not a
plagiarism or AI detector: a student who used an LLM and can explain every decision has
demonstrated understanding, and should score well. A dimension earns its place only if a
student who does *not* understand the work would struggle with it.

✅ **Strong dimensions** require reasoning about *their own specific* submission: tracing
execution on a concrete input, predicting the effect of changing one line, justifying a
decision where another choice was equally valid, explaining why an edge case is or isn't
handled.

⚠️ **Weak dimensions** are answerable from the assignment text alone, or by someone who
skimmed the submission: **questions about syntax**, definitions, "what does this keyword
do", or anything answerable without having reasoned about the work. These are memorizable
and searchable. A syntax-heavy profile still produces exams that *look* completely
reasonable — which is what makes it dangerous, because the loss of signal is invisible.

One dimension worth keeping whatever your field: **counterfactual mutation** ("if I changed
this line to X, what would happen to this input?"). It transfers across every domain and is
one of the hardest things to answer without having reasoned through the code yourself.

> **When reviewing the generated pool, favour questions aimed at points where students
> plausibly did things differently.** A question about a step everyone implements the same
> way becomes the same question for every student with only the names changed — a weak
> probe. A question about a genuine fork in the road adapts to each student's actual choice.
> You cannot always tell in advance, but it is worth watching for.

Transcribe your table into the two blocks below — the first is read when building the question
pool, the second by the examiner at exam time.

<!-- BEGIN: DIMENSIONS -->
<Your dimensions, numbered. Describe each by what it probes, not as a fixed question, and say
where it does NOT apply — otherwise it gets forced everywhere.>
<!-- END: DIMENSIONS -->

<!-- BEGIN: DIMENSION_GUIDE -->
**Dimension Guide (suggested phrasing):**
<One line per dimension, in the exam language, showing how such a question sounds.>
<!-- END: DIMENSION_GUIDE -->

---

## 4. Submission-review conventions

The automated reviewer scores the submission's quality and writes the feedback the student
receives. It was originally written for C, so **it will invent faults if pointed at
different material** — deducting for unchecked `malloc` return values in a garbage-collected
language, or applying programming hygiene to a mathematical proof. This section is what
stops that.

### 4a. What counts as quality in this course

<!-- BEGIN: QUALITY_CRITERIA -->
_(Replace this. Bullet list, in the reviewer's voice. e.g. for a proof-based course:
"- **Rigour:** Is each step justified by a stated theorem or prior result? Are the
  hypotheses of every theorem invoked actually verified?")_
<!-- END: QUALITY_CRITERIA -->

### 4b. What must NOT be penalised

Be generous here — over-listing costs nothing, false deductions cost student goodwill and
create appeals.

**Include your course's presentation/style preferences explicitly.** The reviewer is told
not to penalise style the assignment does not require, but "style" means different things
per course: for code it is comment density, naming, and abstraction choices; for a written
solution it might be notation conventions, how much algebra is shown, or whether steps are
justified in prose or symbols. Name yours, or the reviewer will invent a standard.

<!-- BEGIN: DO_NOT_PENALIZE -->
_(Replace this. e.g. "- No manual memory management — the language is garbage-collected";
"- We do not teach exception handling until week 9; its absence is not a fault";
"- Solutions that skip algebraic steps a competent reader can fill in")_
<!-- END: DO_NOT_PENALIZE -->

### 4c. Authorship markers (Signal B) — optional

Stylistic tells that suggest machine-generated work. It records a note for staff and never
affects any grade.

**We advise against using it.** The exam measures understanding, not who typed the
submission, so this signal sits outside what the system is actually for — we keep it mainly
out of our own interest. It is also the easiest section to get wrong in a way that reads
honest students as suspicious.

If you do want it, describe the tells for your material and include the counter-signals that
indicate human work. Otherwise leave the placeholder text as-is.

<!-- BEGIN: AUTHORSHIP_MARKERS -->
_(Optional — see the Operating Systems profile if you want a worked example.)_
<!-- END: AUTHORSHIP_MARKERS -->

---

## 5. What students implement

**Files students write themselves** _(these get examined)_:

> 

**Files provided in the skeleton** _(never ask ownership questions about these)_:

> 

---

## 6. Exam policy

| Field | Default | Yours |
|---|---|---|
| Exam duration | 16 min (19 with accommodations) | |
| Questions per exam | 3 | |
| Max time per question | ~5 min | |
| Oral / code-quality weighting | 75% / 25% | |
| Which assignments get orally examined | — | |

> ⚠️ **Do not change "questions per exam" without telling us.** Two things are calibrated
> against the number 3: the adaptive-difficulty ladder (which needs at least two
> adjustments to do anything useful) and the understanding verdict (whose thresholds — "at
> least one confident answer", "two or more weak" — are pattern rules over three data
> points). At two questions that rule silently becomes much harsher. The count is
> changeable, but it is a joint decision, not a dial.

---

## 7. Sign-off

The rendered prompts in `rendered/` are what will actually run. Before the course opens,
the course staff must read them and confirm they are appropriate for the course.

| | Name | Date |
|---|---|---|
| Profile written by | | |
| Rendered prompts reviewed by | | |
| Calibration run on past assignment | | |
| **Mock exam sat by course staff (strong submission)** | | |
| **Mock exam sat by course staff (weak submission)** | | |
