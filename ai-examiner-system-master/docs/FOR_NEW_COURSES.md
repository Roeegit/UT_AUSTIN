# Automated Oral Exam — What We Need From a New Course

> For course coordinators and TAs considering adopting the system. What we need from you, how much work it is, and what to decide before the semester.

---

## 1. What the system does

A student submits an assignment. They then sit a ~15-minute, 3-question oral exam in which an AI examiner questions them about their own submission — quoting their variable names, jumping to lines they wrote, asking why they made the choices they made. The system grades the exam, reviews the submission separately, combines the two, emails the student a breakdown, and leaves staff a full audit trail.

It answers one question at class scale: **does this student understand what they submitted?**

Note what it does *not* ask: whether they used AI. A student who used an LLM and can explain every decision scores well; a student who cannot explain their own submission does not. That is intended.

Operating Systems, 2026: ~270 students, 4 assignments, ~550 exam sessions.

---

## 2. Submission format

Every question is anchored to a specific line of the student's submission, highlighted on screen while they answer. What matters is the *form* of the submission, not whether the course teaches programming.

| Submission format | Status |
|---|---|
| Source files in a repository — code, `.tex`, `.md`, `.ipynb` | **Works today** |
| Compiled PDF only | Intake works; nothing to anchor questions to |
| Handwritten or scanned | Needs development |

**Typed submissions work regardless of subject.** A `.tex` proof is text with line numbers, so line highlighting and "explain step 3 of your derivation" work exactly as they do for code.

**Handwritten submissions break two things:** reading the submission requires a vision model, and highlighting a region of an image is different from highlighting a line of text. Both are achievable, neither exists today, and we would want to pilot it on one assignment before committing a course to it.

If your students currently submit on paper, **requiring typed submission removes essentially all of that engineering work** — worth deciding before anything else.

### Getting submissions to us

We collect from GitHub Classroom automatically; repository fetching, re-submissions, roster matching and result storage are all built around it. A Git repository holds any file type, so this works for non-code submissions.

We migrated to GitHub Classroom ourselves this semester — smooth, faster than expected, and students adapted quickly, several preferring it to the previous method.

> **Commit the source, not only a compiled PDF.** A PDF gives us the submission but nothing to anchor a question to. `.tex`, `.md` or `.ipynb` solves both problems at once.

If GitHub Classroom is not possible, tell us early. A different intake path — Drive folder, Moodle export — is real development with schedule risk we cannot currently size, and it affects how students are identified throughout the system.

Whatever the mechanism: one identifiable submission per student, retrievable automatically, with a stable identifier (student ID or university email) matchable to a roster, in machine-readable files.

---

## 3. What we need from you

| | What | When |
|---|---|---|
| 1 | A course profile — what a good question looks like in your field | once |
| 2 | The assignment as students receive it, plus starter material | per examined assignment |
| 3 | Which files students write themselves | per examined assignment |
| 4 | A reviewed question pool | per examined assignment |

Plus, once: a GitHub Classroom org, the student roster, and a decision on which assignments are examined.

**Not needed from you:** writing questions, attending exams, grading, writing feedback, or touching any code or infrastructure.

---

## 4. The course profile (once, at the start)

The system currently thinks like an Operating Systems examiner: it looks for OS/systems concepts and sorts questions into categories that suited us — error handling, API depth, cross-file interaction.

Those categories are the most important setting in the system, because they determine what questions get generated at all. Yours will differ; a mathematical course differs entirely.

The profile is a form covering five things: your field, what "concepts" means in your course, the question categories, your language and notation conventions (so the automated review judges Python as Python rather than as C), and what counts as a "deliverable" in your course.

We provide the form and a meta-prompt you can give to an LLM to draft it. Send us the completed profile with a few past assignments and, ideally, two real past submissions — one strong and one weak. Real submissions matter more than the form does: they show how your students actually write.

We turn that into your course-specific prompts and hand them back. **You then read them and confirm they are right for your course.** They are plain English, not code. If something is wrong for your field, you are the only one who will notice.

### On the question categories

Ours were: design choice, edge case, error handling, API depth, code flow, cross-file interaction, counterfactual mutation.

A linear algebra course would more likely use mathematical justification, numerical stability, complexity, edge cases (singular, non-square, rank-deficient), and verification. An intro programming course might use trace execution, variable state, why this construct, and bug prediction.

A category earns its place if a student who does not understand the work would struggle with it. **Avoid syntax questions** — they are memorisable, searchable, and answerable by someone who merely read the submission. A syntax-heavy profile produces exams that look entirely reasonable while measuring very little.

### Mock exams

Before the course opens, sit one or two complete exams yourselves, using last year's submissions, answering as if you were the student who wrote them.

This surfaces what reading cannot: questions that are unanswerable in five minutes, questions that are trivial for anyone who did the work, whether the difficulty adaptation feels right, and any awkwardness in timing or interface. Bring one strong and one weak submission — problems appear at the edges.

**Time: a few hours for the profile, about an hour per mock exam.** Fixed for the semester after that.

---

## 5. Per examined assignment

Each examined assignment needs a question pool: 20–35 candidates, each tied to a specific file, concept and difficulty, with a citation grounding it in your assignment. The exam draws 3 per student, adapting difficulty as it goes.

**You run the generation prompts yourself** — we supply them with your profile already built in — and send us the finalised pool.

Generation is automatic. The review pass is the actual work, and only you can do it: only you know what your students were taught by week N. The generator can verify a question is grounded in the assignment text; it cannot know a concept is not covered until three weeks later.

For each question, check: is it fair at this point in the semester, is it about something the assignment genuinely required, could a student answer it from the instructions alone, and is it answerable in about five minutes. Delete what fails. Do not rewrite — the pool is generated larger than needed.

Also glance at each question's `excellent_answer` field — a short description, used only by the grader, of what a top answer looks like. Checking it does two things: it confirms the question has real depth (if the best possible answer is only "adequate", cut the question), and your correction of it calibrates how strictly full marks are awarded. This is the main lever you have over grading strictness.

| Step | Time |
|---|---|
| Assignment instructions + starter material | ~0, already exists |
| List the files students write | ~5 min |
| Generate and review the pool | ~30–45 min |
| **Total** | **~45–60 min per examined assignment** |

---

## 6. Courses with weekly assignments

Do not orally examine every assignment. Three approaches, which combine:

1. **Examine 3–4 checkpoints** across the semester. The deterrent comes from students not knowing which assignments will be examined.
2. **Automated review only** in other weeks — no question pool, no scheduling, no student time at all. We ran 237 submissions in a single batch this way.
3. **Group 2–3 assignments into one exam.** Pool size is driven by the variety one 3-question exam needs (~25 questions), not by the number of assignments.

A 12-assignment course needs 3–4 pools, not 12.

---

## 7. Decisions to make together

1. Submission format (§2)
2. Which assignments are examined
3. Weight of the oral exam — we used 75% oral / 25% submission quality within the assignment grade
4. Scheduling — students book slots; we cross-reference bookings against attendance
5. Accommodations — extended time is automatic from an ID list, which we need from you
6. Reserve duty and exemption policy
7. Exam language — Hebrew or English

### Two tradeoffs worth deciding deliberately

**Questions per exam × time per question.** We ran 3 × 5 minutes. 2 × 8 gives deeper questions and less coverage; 4 × 4 the reverse.

Two constraints make 3 a floor rather than a default. Difficulty adapts after each answer, so three questions give two adjustments and two give one — at two, the adaptation barely operates. And the understanding verdict is a pattern across questions ("at least one confident answer", "two or more weak"), calibrated for three data points; at two questions "two or more weak" silently becomes "both", a materially harsher rule. Changing the count means recalibrating with us.

Longer questions win where a question needs reading before it can be answered — a mathematical derivation is the clear case.

**Exam length × number of assignments examined.** More exam events dilute a student's bad day and apply the deterrent more often; against that, scheduling load and your review time. We suggest more events at the 3-question floor rather than fewer and longer.

---

## 8. Summary of effort

**Once, before the semester:** course profile plus past material (a few hours) · read and sign off the generated prompts (~1h) · 1–2 mock exams (~1h each) · decisions from §7 (~1h)

**Per examined assignment:** ~45–60 minutes.

---

## 9. Further reading

- `SYSTEM_QUALITIES.md` — what the system does and the design decisions behind it. Written for staff, not developers.
- `TECHNICAL_SPEC.md` — architecture and implementation. For developers.
