# Generated prompts — do not edit these files

Every `.txt` here is built from `courses/_shared/*_skeleton.txt` + `../COURSE_PROFILE.md`.
Editing one directly works until the next render, which overwrites it without warning.

To change any of them, edit the **profile** and re-run:

    python courses/render.py operating-systems

`python courses/render.py operating-systems --check` verifies these files are up to date and writes
nothing — use it in CI to catch a profile edit that was never rendered.

**Course staff:** these files are the text that actually runs at exam time. Read them and sign
off before the course opens.

| file | built from |
|---|---|
| `examiner_prompt.txt` | `_shared/examiner_skeleton.txt` |
| `grader_prompt.txt` | `_shared/grader_skeleton.txt` |
| `submission_reviewer_prompt.txt` | `_shared/submission_reviewer_skeleton.txt` |
| `reviewer_validator_prompt.txt` | `_shared/reviewer_validator_skeleton.txt` |
| `pool_step1_prompt.txt` | `_shared/pool_step1_skeleton.txt` |
| `pool_step2_prompt.txt` | `_shared/pool_step2_skeleton.txt` |
