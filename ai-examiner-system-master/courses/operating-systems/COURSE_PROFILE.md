# Course Profile — Operating Systems

> **This is the worked example.** It is the profile the system actually ran on in 2026
> (~270 students, 4 assignments, ~550 exams). Hand it to a new course alongside the blank
> form in `_template/` so they can see a filled-in one.
>
> Values live between the `BEGIN:`/`END:` markers — `render.py` reads those and nothing else,
> so prose outside them is free-form and safe to edit.

---

## 1. Course identity

<!-- BEGIN: COURSE_NAME -->
Operating Systems
<!-- END: COURSE_NAME -->

<!-- BEGIN: EXAM_LANGUAGE -->
Hebrew
<!-- END: EXAM_LANGUAGE -->

| Field | Value |
|---|---|
| Course ID / folder slug | `operating-systems` |
| Submission language | C, shell |
| What students submit | source files in a GitHub Classroom repo |

---

## 2. What "concepts" means in this course

<!-- BEGIN: DOMAIN_CONCEPTS -->
   The relevant concepts are OS / systems concepts: processes and process lifecycle,
   system calls and their failure modes, file descriptors and I/O, signals, concurrency
   and synchronisation, scheduling, and inter-process communication.
<!-- END: DOMAIN_CONCEPTS -->

---

## 2b. Submission structure

What this course's work is physically made of, so the generator knows what it is analysing
and what a well-formed `focus` looks like here.

<!-- BEGIN: SUBMISSION_STRUCTURE -->
In this course a student's submission is a set of SOURCE FILES in a Git repository.

  - A "deliverable" is one source file the student writes (e.g. `ex3.c`, `src/part2.c`).
  - A "component" within a deliverable is a function or a logical block of code — use the
    names the assignment or skeleton gives (`main`, `handle_signal`, the argument-parsing
    block).
  - Deliverables often DO depend on one another: one file's output is consumed by another,
    or they share state through a file, pipe, or shared variable.

Example of a well-formed `focus` in this course:
  "the stdin-handling step that lets the runner feed the same input to several hooks"
  — names the mechanism AND the context it appears in. Contrast with "stdin" (too bare)
  or "the if on line 42" (a location, not an element).
<!-- END: SUBMISSION_STRUCTURE -->

<!-- BEGIN: STARTER_MATERIAL -->
2. SKELETON / STARTER MATERIAL — everything handed to students BEFORE they do any work:
   stubs, fully-provided material they are not expected to author, and any starter
   templates. A student cannot be asked to defend a line they did not write, so separating
   this from their own work is a precondition for a fair question.
<!-- END: STARTER_MATERIAL -->

### 2c. Grounding phrase

Appended by the examiner to conceptual questions, to force the answer to be grounded in the
student's own submission. Must be written in the exam language.

<!-- BEGIN: DEMAND_SPECIFICS -->
"בתשובתך, התייחס לשמות המשתנים שבקוד שלך." (In your answer, refer to the variable names in your code.)
<!-- END: DEMAND_SPECIFICS -->

---

## 3. Question dimensions

> ⚠️ **This section feeds two prompts at once** — the question generator (which decides what
> questions exist) and the examiner (which decides how they are phrased at exam time). That
> is deliberate: they are the same taxonomy, and if they were maintained separately they
> would drift, leaving the examiner reaching for OS phrasing on a non-OS question. Edit here
> and re-render; never edit the rendered prompts directly.

### 3a. Dimension definitions — used by the question generator

<!-- BEGIN: DIMENSIONS -->
THE SEVEN DIMENSIONS  (each is described by INTENT — phrase the actual question yourself,
adapted to the assignment; the examiner will adapt further to the student's code)

1. design_choice — probe WHY the student chose one viable approach over the alternatives
   they realistically had. Only valid where the student actually had a choice.
2. edge_case — probe how the code behaves on a boundary or unusual input the assignment
   makes relevant.
3. error_handling — probe whether failures of an operation the assignment requires are
   detected and what the student's code does when they occur.
4. api_depth — probe genuine understanding of the behaviour/parameters of a mechanism the
   student deliberately used, tied to a consequence in their own program.
5. code_flow — probe the student's ability to trace their own logic on a concrete input
   the assignment makes meaningful.
6. cross_file / cross-component — probe how parts interact across a boundary, or how one
   operation affects a later operation on the same data/state.
7. counterfactual_mutation — probe cause-and-effect in the student's OWN code by positing a
   SMALL, concrete edit to a line or two they wrote (replace a statement / operator /
   argument, delete a line, or reorder two adjacent lines) and asking how a specific, named
   input's behaviour or output would change as a result. This is the operational form of the
   "reason about a hypothetical MODIFICATION" goal: it separates a student who can describe
   what their code does from one who can predict what a targeted change would do, and it
   exposes reliance on code they did not reason through. Valid only where the edit has a
   determinate, traceable effect the student can derive by hand — keep the mutation to one or
   two lines and the input small so the answer stays within the ~5-minute budget; avoid
   mutations that force re-deriving a large output, depend on unspecified parts of the
   student's code, or whose effect is trivially obvious.
<!-- END: DIMENSIONS -->

### 3b. Phrasing guide — used by the examiner at exam time

List here the dimensions that **actually appear in generated pools**. A phrasing entry for a
dimension the generator never produces is dead weight in the examiner's context — it is one
more pattern the model can reach for when it was handed a different dimension.

<!-- BEGIN: DIMENSION_GUIDE -->
**Dimension Guide (Suggested phrasing in Hebrew):**
- design_choice: "למה בחרת בגישה הזו?" (Why did you choose this approach?)
- edge_case: "מה קורה אם [קלט חריג]?" (What happens if [edge case input]?)
- error_handling: "מה קורה אם [system call] נכשל?" (What happens if [system call] fails?)
- api_depth: "מה בדיוק מחזיר [system call] במקרה הזה?" (What exactly does [system call] return here?)
- code_flow: "נניח שהקלט הוא [ערכים]. תעקוב אחרי הביצוע שורה אחר שורה." (Trace the execution line by line for [values].)
- cross_file: "איך [קובץ A] מעביר מידע ל-[קובץ B]?" (How does [File A] pass info to [File B]?)
<!-- END: DIMENSION_GUIDE -->

> **Known gap — `counterfactual_mutation` is defined in 3a but deliberately absent here.**
> Across all three 2026 pools (**127 questions**) the generator produced it **zero** times,
> so the examiner is never handed it. Its validity bar in 3a is far stricter than the other
> six (determinate traceable effect, one-to-two lines, not trivially obvious, answerable in
> five minutes), and the generator appears to self-censor rather than risk a weak question.
>
> This needs resolving one way or the other during the next calibration — either loosen the
> definition so it gets generated (it is conceptually the strongest ownership probe we have),
> or drop it from 3a. Do **not** resolve it by adding phrasing here; that treats the symptom.

---

## 4. Submission-review conventions

<!-- BEGIN: QUALITY_CRITERIA -->
- **Resource hygiene (C assignments):** Are return values of `open()`, `read()`, `write()`, `malloc()`, `fork()`, `waitpid()`, etc. checked? Is memory freed properly?
<!-- END: QUALITY_CRITERIA -->

<!-- BEGIN: DO_NOT_PENALIZE -->
- Comment density, variable naming style, abstraction choices, or use of helper functions — none of these are specified by the assignment
- Platform-specific choices that are correct on the target platform (e.g., GNU `find -printf` on a Linux assignment, Linux-specific syscalls)
- Helpers that the assignment itself provided as `void` or otherwise un-checkable — do not demand return-value checks on a function that returns nothing
- Constructs the assignment spec explicitly mandates, even where they would be unusual otherwise
<!-- END: DO_NOT_PENALIZE -->

> **This list is meant to grow.** Entries get added whenever the reviewer is found
> penalising something the student had no choice about — most often material the assignment
> provided, or a construct the spec mandated. Expect to discover your course's own
> equivalents during calibration and after the first run.

### 4c. Authorship markers (Signal B)

The stylistic tells that suggest machine generation. These are **highly** domain-specific —
a mathematical submission has entirely different tells from a C file.

<!-- BEGIN: AUTHORSHIP_MARKERS -->
**Markers to look for:**
- **LLM Conversational & Prompt Artifacts :** Actively scan for any text or comments that break the natural context of a source code file. These include:
  * **Prompt Echoing:** Meta-comments that read like instructions, constraints, or stylistic rules given *to* the author, rather than explanations of the code itself (e.g., "all comments are casual and laconic, no caps at start", "make sure it's under 300 lines").
  * **Conversational Residue:** Leftover AI chat text accidentally pasted into the file (e.g., "Certainly! Here is the implementation...", "```c").
  * **AI-Style Disclaimers:** Overly formal caveats that AIs generate to hedge their bets (e.g., "Note: This assumes a standard runtime environment", "Note: results may vary depending on your setup").
  * **Hallucinated Placeholders:** Code blocks skipped for brevity (e.g., `// ... rest of the code remains the same ...`).
  * **OVERRIDE COMMAND:** If you detect ANY of these artifacts, you MUST immediately output `"level": "high"` and flag it in your analysis. This overrides any counterbalancing "human" mistakes.
- **Hyper-uniformity:** Unusually uniform formatting and consistent comment style across the entire file.
- **Over-engineered error handling:** Professional-grade diagnostic messages beyond what the assignment requires.
- **Perfect Abstraction:** Logically perfect but over-abstracted helper functions that a student under deadline pressure would not naturally write.
- **Sterile Codebase:** No commented-out debug lines, no dead code, no TODO stubs — suspiciously clean for student work.
- **Naming Conventions:** Variable naming conventions that are unusually consistent and professional for student code.
- Overly complete `#include` lists or defensive guard patterns that go beyond the assignment's scope.
- Conversely: presence of commented-out debug prints, inconsistent style, TODO comments, variable naming that drifts between conventions — these are signals of human authorship.


<!-- END: AUTHORSHIP_MARKERS -->

---

## 5. Exam policy

| Field | Value |
|---|---|
| Exam duration | 16 min (19 with accommodations) |
| Questions per exam | 3 |
| Max time per question | ~5 min |
| Oral / code-quality weighting | 75% / 25% |
| Assignments orally examined | 1, 2, 3 (assignment 4 was code-review only) |
