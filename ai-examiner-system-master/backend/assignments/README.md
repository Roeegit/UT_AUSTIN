# Per-assignment resources

Loaded on demand by `main._get_assignment_resources()`, which builds the path as
`assignments/{assignment_name}_{resource}`. Because the assignment name may itself contain a
slash, a **namespaced** assignment lands in a course subdirectory with no code involved:

```
assignments/
├── assignment-3_readme.md                 # legacy, flat — Operating Systems
├── assignment-3_question_pool.json
├── …
└── linear-algebra/                        # namespaced: "linear-algebra/hw1"
    ├── hw1_readme.md
    ├── hw1_question_pool.json
    ├── hw1_pool_raw.json                  # generator intermediate, not read at runtime
    └── hw1_ta_report.json                 # human review punch-list, not read at runtime
```

**New assignments should be namespaced** `<course>/<assignment>` (MULTI_COURSE_MIGRATION §4.2) —
it prevents two courses colliding on `assignment-1` in the database, in GCS and in the retake
lock, and it organises this directory for free.

The 2026 Operating Systems assignments stay flat deliberately. Their names are recorded in the
sessions table, in GCS paths and in result blobs; renaming them would orphan that data for no
benefit.

Resources per assignment:

| Suffix | Required | Read at runtime |
|---|---|---|
| `_readme.md` | yes | yes — the assignment instructions given to examiner and reviewer |
| `_question_pool.json` | yes | yes — the question pool (`validate_no_conflicts` runs on load) |
| `_man_pages.txt` | no | yes, if present |
| `_files.json` | no | yes, if present |
| `_pool_raw.json`, `_ta_report.json` | no | no — generation artefacts, kept for review |
