"""
submission_source.py — one intake surface over several submission mechanisms.

GitHub Classroom and Google Forms run side by side: routing is per assignment, so a
GitHub course and a Forms course can be served by the same deployment at the same time.
Adding a Forms assignment is a config.FORM_SOURCES entry; everything not listed there
continues to go to GitHub exactly as before.

    from submission_source import fetch_and_save_submission, load_local_submission

Both adapters write the identical GCS layout — {assignment}/{student_key}/{filename} —
so build_exam_context, the graders and the admin views need no knowledge of where a
submission came from.

`student_key` is whatever identifies the student for that source: a github_username for
GitHub, the 9-digit university ID for a Form. See MULTI_COURSE_MIGRATION §4.3c for why
that eventually becomes a first-class prefixed key rather than a bare string.

Note on imports: github_stub builds a GCS client at import time, so it is imported
inside the functions here rather than at module scope. That keeps routing decisions and
the Forms path usable offline (tests, scripts, admin tooling) without credentials, and
leaves github_stub itself untouched.
"""

from __future__ import annotations

import forms_stub

GITHUB = "github"
GOOGLE_FORM = "google_form"


def source_for(assignment_name: str) -> str:
    """Which mechanism serves this assignment. GitHub is the default, so existing
    assignments keep working with no config change."""
    return GOOGLE_FORM if forms_stub.is_form_assignment(assignment_name) else GITHUB


def serves_github(assignment_names) -> bool:
    """Does this deployment serve any GitHub-intake assignment at all?

    Gates the GitHub-only startup work (the username→ID fallback map, the stored-username
    format check). Keyed on intake mechanism rather than on COURSE_ID, because "is this a
    Forms course" is the wrong question — a future course could collect via GitHub, and a
    single deployment can serve both at once.
    """
    return any(source_for(a) == GITHUB for a in assignment_names)


def fetch_and_save_submission(student_key: str, assignment_name: str):
    """Pull the student's submission into GCS. Returns the adapter's FetchResult —
    both expose .files_saved / .files_missing / .success."""
    if source_for(assignment_name) == GOOGLE_FORM:
        return forms_stub.fetch_and_save_submission(student_key, assignment_name)
    import github_stub
    return github_stub.fetch_and_save_submission(student_key, assignment_name)


## def load_local_submission(student_key: str, assignment_name: str) -> dict[str, str]:
##   """Read the previously fetched files back from GCS."""
##   if source_for(assignment_name) == GOOGLE_FORM:
##        return forms_stub.load_local_submission(student_key, assignment_name)
##    import github_stub
##    return github_stub.load_local_submission(student_key, assignment_name) ##


def load_local_submission(student_key, assignment_name):
    import os
    files = {}
    
    # Pointing directly to your exact folder location
    base_dir = r"C:\Users\הניה\Desktop\ai_examiner\submissions"
    
    # Check both submissions/Rohithk01 and submissions/Rohithk01/austin-a
    sub_dir = os.path.join(base_dir, student_key)
    target_dir = os.path.join(sub_dir, assignment_name) if os.path.exists(os.path.join(sub_dir, assignment_name)) else sub_dir
    
    if os.path.exists(target_dir):
        for fname in os.listdir(target_dir):
            fpath = os.path.join(target_dir, fname)
            if os.path.isfile(fpath):
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    files[fname] = f.read()
    return files


# def build_exam_context(assignment_readme: str, student_files: dict[str, str]) -> str:
#     """Source-agnostic — both adapters produce the same {filename: content} dict."""
#     import github_stub
#     return github_stub.build_exam_context(assignment_readme, student_files)

def build_exam_context(assignment_readme: str, student_files: dict[str, str]) -> str:
    parts = []
    if assignment_readme:
        parts.append(f"# Assignment Instructions\n\n{assignment_readme.strip()}")
    for filename, content in student_files.items():
        if filename == "README.md":
            continue
        parts.append(f"# File: {filename}\n```\n{content}\n```")
    return "\n\n".join(parts)

def fetch_id_file(student_key: str, assignment_name: str) -> tuple[str | None, str | None]:
    """The student's identity payload, in the shape main._parse_id_txt expects:
    (content, error) with exactly one of them set.

    GitHub: read id.txt out of the repo, as before.
    Forms:  there is no id.txt — the 9-digit university ID *is* the form field the
            student submitted under, so hand that back directly. _parse_id_txt then
            resolves it exactly as it would a well-formed id.txt.
    """
    if source_for(assignment_name) == GOOGLE_FORM:
        digits = "".join(c for c in (student_key or "") if c.isdigit())
        return (digits, None) if digits else (None, "no university ID on the form response")
    import github_stub
    return github_stub.fetch_single_file(student_key, assignment_name, "id.txt")


def student_name(student_key: str, assignment_name: str) -> str | None:
    """The student's own name as the source supplies it, or None if it cannot.

    Forms: whatever they typed in the configured name field.
    GitHub: None — a repo carries only a username, so the name has to come from a roster.

    Never raises: a name is a nicety on top of an already-graded exam, and a Sheets hiccup
    must not cost a student their grade email.
    """
    try:
        if source_for(assignment_name) == GOOGLE_FORM:
            return forms_stub.name_for(student_key, assignment_name)
    except Exception as exc:  # noqa: BLE001
        print(f"[name] could not read the form name for {student_key!r}: {exc}")
    return None


def submission_exists(student_key: str, assignment_name: str) -> bool:
    """Cheap pre-exam check: has this student submitted at all?

    For Forms this is a sheet lookup. For GitHub there is no equally cheap check —
    resolving the repo costs an API round trip — so callers on the GitHub path should
    keep using the existing lookup logic in main.py rather than this helper.
    """
    if source_for(assignment_name) == GOOGLE_FORM:
        return forms_stub.submission_exists(student_key, assignment_name)
    raise NotImplementedError(
        "submission_exists is Forms-only; the GitHub path uses main.py's repo lookup")


def list_submitted(assignment_name: str) -> list[str]:
    """Every student key with a submission — roster reconciliation, admin views.
    Forms-only: GitHub has no listing without enumerating the org's repos."""
    if source_for(assignment_name) == GOOGLE_FORM:
        return forms_stub.list_submitted_ids(assignment_name)
    raise NotImplementedError("list_submitted is Forms-only")
