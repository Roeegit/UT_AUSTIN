# Course Profile — Linear Algebra 1

> Authored by the Linear Algebra course staff (2026-08-06). This is the runtime copy that
> `render.py` reads; the staff's original is kept alongside as
> `COURSE_PROFILE-linear-algebra-1.md`. Two edits were made to it here, both marked ⚙ below:
> an `AUTHORSHIP_MARKERS` block (structurally required by the reviewer skeleton — configured
> OFF, as the staff do not want authorship tested), and `DEMAND_SPECIFICS` translated to
> Hebrew, because the examiner appends it verbatim to a question that must be in Hebrew.

## 1. Course identity

<!-- BEGIN: COURSE_NAME -->
Linear Algebra 1
<!-- END: COURSE_NAME -->

<!-- BEGIN: EXAM_LANGUAGE -->
Hebrew
<!-- END: EXAM_LANGUAGE -->

| Field | Value |
|---|---|
| Course ID / folder slug | `linear-algebra` |
| Submission language | Hebrew prose and LaTeX mathematics |
| What students submit | One Markdown file per homework assignment, containing the student's written solutions |

---

## 2. What "concepts" means in this course

<!-- BEGIN: DOMAIN_CONCEPTS -->
The relevant concepts include fields and field arithmetic, systems of linear equations,
Gaussian elimination and row-equivalent matrices, matrices and matrix operations, invertibility,
vector spaces and subspaces, linear combinations and span, linear dependence and independence,
bases and dimension, coordinates, rank, row space, column space and null space, and linear
transformations, including kernel, image, composition and matrix representation.

The course gives importance to both technical skill and theoretical understanding. Students are
expected not only to perform calculations correctly, but also to understand why a method works,
explain the meaning of the result, connect it to the relevant definitions and theorems, and write
a clear and logically correct mathematical argument.

A question is fair only if the student's assignment genuinely required the relevant concept and
if that concept had already been taught when the assignment was given. Prefer the concept the
student actually used over a more advanced concept that can be connected to the exercise only in
hindsight.

This list is the whole semester. Each assignment is set at one point in it, and a separate
"concepts in scope for this assignment" list is supplied alongside the assignment itself when
one is defined. Where it is, it is authoritative: it says what the students had actually been
taught by then, and questions stay inside it.
<!-- END: DOMAIN_CONCEPTS -->

---

## 2b. Submission structure

<!-- BEGIN: SUBMISSION_STRUCTURE -->
In this course, a student's submission is a WRITTEN SOLUTION SET in one Markdown file, using
LaTeX for mathematical expressions. The file contains the student's solutions to all numbered
exercises in one homework assignment.

- A "deliverable" is one numbered exercise or sub-exercise, for example "exercise 3(b)".
- A "component" is a meaningful part of the solution: a claim, a computation, a row operation,
  a case split, an application of a definition or theorem, or a conclusion.
- Exercises are independent unless the assignment explicitly connects them, for example by
  asking the student to use the result of an earlier part.
- A question must identify both the mathematical step and its context. It should not refer only
  to a line number or only to a general topic.

Example of a good focus:
"the step in exercise 3(b) where the student concludes from the reduced matrix that the system
has a free variable."

The submission may contain transcription or LaTeX artefacts. These are not evidence about the
student's mathematical understanding and must not affect the score.
<!-- END: SUBMISSION_STRUCTURE -->

### 2d. Starter material

What, if anything, students are handed before they begin. A code course provides stubs and
files the student did not author, and the question generator must not ask them to defend
those. This course provides nothing, so the block says so once, here — rather than the person
generating a pool having to state it every time.

<!-- BEGIN: STARTER_MATERIAL -->
2. STARTER MATERIAL — there is none in this course. Students receive only the exercise sheet
   and write every part of the solution themselves, so every line of a submission is the
   student's own work and is fair game for a question. Do not expect, ask for, or reason about
   provided templates or stubs.
<!-- END: STARTER_MATERIAL -->

### 2c. Grounding phrase

⚙ Translated from the staff's English original. The examiner appends this verbatim to
`questionText`, and the same prompt requires that text to be strictly Hebrew — an English
sentence would appear untranslated mid-question. Staff should adjust the wording to their voice.

<!-- BEGIN: DEMAND_SPECIFICS -->
"בתשובתך, התייחס לשלב המדויק בפתרון שלך שעליו נשאלת השאלה."
<!-- END: DEMAND_SPECIFICS -->

---

## 3. Question dimensions

### 3a. Dimension definitions — used by the question generator

<!-- BEGIN: DIMENSIONS -->
Each question should have one main dimension from the list below. Across the full question pool,
questions should also be balanced along four independent properties:

- mathematical nature: theoretical, technical, or a combination of both;
- difficulty: easy, medium, or hard;
- scope: local, focusing on one step, or broad, requiring connections across several topics;
- relation to the submission: directly about the student's solution, or about a small change to
  the assumptions, objects or method used in that solution.

THE EIGHT DIMENSIONS

1. conceptual_understanding — probe the mathematical meaning or intuition behind a result,
   definition, object or procedure used in the student's solution. The student should explain
   what the result says, not only repeat a formula or calculation.

2. technical_execution — probe whether the student can reproduce, trace or check a calculation
   from their own solution, such as row reduction, matrix multiplication, solving a system or
   finding coordinates. Keep the calculation small enough to complete orally.

3. justification_and_formal_reasoning — probe why a specific step is valid, which definition,
   theorem or previous result supports it, and whether the required assumptions hold. This
   dimension may also test correct logical structure and precise mathematical writing.

4. theory_technique_connection — probe the connection between a technical procedure and the
   theory behind it. For example, ask why row operations preserve the solution set, or how the
   number of pivots is connected to rank or dimension.

5. completeness_and_precision — probe whether the solution proves exactly what was asked. This
   includes all required cases, both directions of an equivalence, both inclusions in a set
   equality, or the distinction between finding some solutions and finding all solutions.

6. method_choice — probe why the student chose one valid method rather than another and whether
   they understand the advantages, limitations and assumptions of each method. Use this only when
   the student genuinely had more than one reasonable approach.

7. broad_connections — probe whether the student can connect the specific exercise to other
   concepts already studied in the course. The question should require a broader view of the
   material, but it must remain answerable using only material taught by that point in the course.

8. counterfactual_mutation — make one small and clear change to the student's problem or solution,
   such as changing a hypothesis, field, matrix size, coefficient, dependence assumption or row
   operation. Ask what changes, what remains true, or which step of the original solution fails
   first and why. The effect of the change must be determinate and manageable by hand.

Avoid questions that only ask the student to state a definition or theorem from memory. A good
question should be difficult for a student who does not understand their own submitted solution.
<!-- END: DIMENSIONS -->

### 3b. Phrasing guide — used by the examiner at exam time

<!-- BEGIN: DIMENSION_GUIDE -->
**Dimension Guide (suggested phrasing):**

- conceptual_understanding: "What is the mathematical meaning of the result you obtained here? How would you explain it without doing another calculation?"
- technical_execution: "Repeat the calculation in this step and explain what you are doing at each main transition."
- justification_and_formal_reasoning: "Why is this step valid? Which definition or result supports it, and which assumptions are needed?"
- theory_technique_connection: "How is your calculation connected to the theoretical result you used? Why does the method work here?"
- completeness_and_precision: "What exactly have you proved here, and how do you know that you covered all cases or all solutions?"
- method_choice: "Why did you choose this method? What other method could you have used, and what would be different?"
- broad_connections: "How is this step connected to other concepts studied earlier in the course?"
- counterfactual_mutation: "Suppose we change the [assumption/coefficient/field/matrix] in the following way. What changes in your solution, and which step is affected first?"
<!-- END: DIMENSION_GUIDE -->

---

## 4. Submission-review conventions

<!-- BEGIN: QUALITY_CRITERIA -->
- **Mathematical correctness:** Are the claims, computations and final conclusions correct?
- **Technical accuracy:** Are matrix operations, row operations, algebraic manipulations and
  parameterisations carried out correctly?
- **Conceptual understanding:** Does the solution show understanding of the mathematical meaning,
  rather than only applying a memorised procedure?
- **Rigour and formal writing:** Are non-trivial steps justified? Are definitions and theorems used
  correctly, with their assumptions checked? Is the logical structure clear and valid?
- **Completeness and precision:** Does the solution address every required part, case and direction,
  and does it prove exactly the requested statement?
- **Connection between theory and technique:** When relevant, does the student connect the
  computation to the theoretical result that explains it?
<!-- END: QUALITY_CRITERIA -->

<!-- BEGIN: DO_NOT_PENALIZE -->
- Routine algebraic steps that a competent reader can easily complete, unless the missing step is
  the main mathematical point of the exercise.
- A correct solution that uses a different valid method from the expected solution.
- A method that is less elegant or less efficient, as long as it is mathematically correct and
  answers the question.
- Standard notation variants, as long as the student is internally consistent and the meaning is
  clear.
- Mixing Hebrew and English, or mixing prose and mathematical notation.
- A brief but correct justification of a standard step, unless the exercise specifically asks for
  a formal proof or for the justification of that step.
- Minor formatting, Markdown or LaTeX issues that do not change the mathematical meaning.
- Transcription artefacts or unclear tokens created when converting handwriting to text.
<!-- END: DO_NOT_PENALIZE -->

> **This list is meant to grow.** Entries get added whenever the reviewer is found
> penalising something the student had no choice about — most often material the assignment
> provided, or a construct the spec mandated. Expect to discover your course's own
> equivalents during calibration and after the first run.

### 4c. Authorship markers (Signal B)

⚙ Added here — the submission-reviewer skeleton requires this block and `render.py` fails
without it. Configured OFF at the staff's request: they do not want authorship tested. It is
also the right setting on the merits, since every submission in this course is machine-produced
by design (students hand-write, then have an LLM transcribe), so uniform formatting and clean
notation are properties of the transcription step and carry no information about who did the
mathematics. Treating them as signals would flag the entire cohort.

<!-- BEGIN: AUTHORSHIP_MARKERS -->
**This course defines no authorship markers. Report `"level": "none"` and `"markersFound": 0`
in all cases.**

Do not treat formatting, notation consistency, LaTeX quality, phrasing style or structural
uniformity as evidence of anything: every submission is transcribed from handwriting by a
language model, so those properties describe the transcriber and not the student.

The single exception is direct conversational residue from a chat assistant left in the
submission (for example "Certainly! Here is the proof...", "Let me know if you'd like me to
elaborate"). Report that if you see it, and nothing else.
<!-- END: AUTHORSHIP_MARKERS -->

## 5. Exam policy

| Field                             | Value                           |
|-----------------------------------|---------------------------------|
| Exam duration                     | 22 min (28 with accommodations) |
| Questions per exam                | 4                               |
| Max time per question             | ~5 min                          |
| Oral / solution-quality weighting | 75% / 25%                       |
| Assignments orally examined       | 3, 7, 9-10                      |

> ⚠ **The exam-policy table is not yet wired up.** These values are read by humans, not by
> `render.py` — no placeholder pulls from them. The question count of 3 and the 15-minute
> duration are hardcoded in `courses/_shared/examiner_skeleton.txt`, `grader_skeleton.txt`,
> `main.py` (`total_questions`) and the frontend's "שאלה {n} מתוך 3" label. Moving to 4
> questions / 22 minutes is a code + skeleton change affecting Operating Systems too, and the
> grader's score bands are calibrated for three answers. See the migration notes before changing.
