# Per-course material

Everything in this tree is **course-specific**. Everything the courses share — the exam
mechanics, fairness rules, distress handling, IRT scoring, JSON schemas — lives in
`_shared/` and is never forked per course.

```
courses/
├── _shared/                    # course-AGNOSTIC skeletons (owned by the system maintainers)
│   ├── examiner_skeleton.txt
│   ├── grader_skeleton.txt
│   ├── submission_reviewer_skeleton.txt
│   ├── pool_step1_skeleton.txt
│   └── pool_step2_skeleton.txt
├── _template/
│   ├── COURSE_PROFILE.md       # ← the form a new course fills in (once)
│   └── PROFILE_META_PROMPT.md  # ← hand this + the form to an LLM to draft the profile
└── <course-id>/
    ├── COURSE_PROFILE.md       # the course's filled-in profile (the SOURCE OF TRUTH)
    ├── rendered/               # generated = skeleton + profile. THIS IS WHAT ACTUALLY RUNS.
    │   ├── examiner_prompt.txt
    │   ├── grader_prompt.txt
    │   ├── submission_reviewer_prompt.txt
    │   ├── pool_step1_prompt.txt
    │   └── pool_step2_prompt.txt
    └── assignments/            # per-assignment README + question pool JSON
```

## Why skeleton + profile, and not a separate copy per course

The shared 80–95% is where the machinery that protects students lives: the strict
distress-detection criteria, the anti-pedantry rules, the poker-face constraints, the
authorship signal table, prompt-injection handling. If each course forked a full copy of
every prompt, those would silently diverge — and a fix made after a course forked would
never reach it. Bugs in exactly that shared material are the ones that hurt students.

So the shared part has **one** definition, and courses supply only their own domain.

## Why `rendered/` is committed anyway

The TA has to be able to read *exactly* what will run and sign off on it — a profile alone
does not show them that. So the render is materialized to disk, reviewed, and committed.
Single source of truth for the shared rules; full transparency for the course staff.

**Never hand-edit `rendered/`.** Edit `COURSE_PROFILE.md` and re-render, or the next render
silently discards the change.

## Adding a course

1. Copy `_template/COURSE_PROFILE.md` to `courses/<course-id>/COURSE_PROFILE.md`.
2. The course TA/lecturer fills it in (see `PROFILE_META_PROMPT.md` for LLM-assisted drafting).
3. Render the prompts.
4. **Calibrate:** run the pool generator on one *past* assignment, read ~20 generated
   questions with the TA, adjust the profile, re-render. Two or three rounds is normal.
5. TA signs off on `rendered/`.
