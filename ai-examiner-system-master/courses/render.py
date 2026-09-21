#!/usr/bin/env python3
"""
render.py -- build a course's runtime prompts from the shared skeletons + its profile.

    python courses/render.py operating-systems
    python courses/render.py operating-systems --check    # verify, write nothing (CI)

Reads   courses/_shared/*_skeleton.txt
        courses/<course>/COURSE_PROFILE.md
Writes  courses/<course>/rendered/*.txt

Values are pulled from the profile between markers:

    <!-- BEGIN: DIMENSIONS -->
    ...
    <!-- END: DIMENSIONS -->

Every {{PLACEHOLDER}} in a skeleton must have a matching block, and every block must be
used by at least one skeleton -- both directions are errors, because a silently unsubstituted
placeholder ships an exam prompt containing the literal text "{{DIMENSION_GUIDE}}".

Standard library only.
"""

import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SHARED = HERE / "_shared"

SKELETONS = {
    "examiner_skeleton.txt": "examiner_prompt.txt",
    "grader_skeleton.txt": "grader_prompt.txt",
    "submission_reviewer_skeleton.txt": "submission_reviewer_prompt.txt",
    "reviewer_validator_skeleton.txt": "reviewer_validator_prompt.txt",
    "pool_step1_skeleton.txt": "pool_step1_prompt.txt",
    "pool_step2_skeleton.txt": "pool_step2_prompt.txt",
}

BLOCK_RE = re.compile(
    r"<!--\s*BEGIN:\s*([A-Z_]+)\s*-->\n(.*?)<!--\s*END:\s*\1\s*-->",
    re.S,
)
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_]+)\}\}")

# Provenance lives in rendered/README.md, NOT at the top of each prompt.
#
# It used to be a "### GENERATED FILE -- DO NOT EDIT ###" banner inside every file, which put
# build metadata and a line addressed to course staff ("read it and sign off") into the system
# prompt the model actually receives, and forced anyone pasting a prompt by hand to strip four
# lines first — silently changing the prompt if they forgot.
README = """\
# Generated prompts — do not edit these files

Every `.txt` here is built from `courses/_shared/*_skeleton.txt` + `../COURSE_PROFILE.md`.
Editing one directly works until the next render, which overwrites it without warning.

To change any of them, edit the **profile** and re-run:

    python courses/render.py {course}

`python courses/render.py {course} --check` verifies these files are up to date and writes
nothing — use it in CI to catch a profile edit that was never rendered.

**Course staff:** these files are the text that actually runs at exam time. Read them and sign
off before the course opens.

| file | built from |
|---|---|
{table}
"""


def load_profile(course_dir):
    path = course_dir / "COURSE_PROFILE.md"
    if not path.exists():
        sys.exit(f"ERROR: no COURSE_PROFILE.md in {course_dir}")
    text = path.read_text(encoding="utf-8")
    blocks = {name: body.rstrip("\n") for name, body in BLOCK_RE.findall(text)}
    if not blocks:
        sys.exit(f"ERROR: {path} contains no <!-- BEGIN: X --> blocks")
    return blocks


def render_one(skel_name, blocks):
    skel = (SHARED / skel_name).read_text(encoding="utf-8")
    needed = set(PLACEHOLDER_RE.findall(skel))
    missing = sorted(needed - set(blocks))
    if missing:
        sys.exit(
            f"ERROR: {skel_name} needs {missing}, but the profile defines no such block(s).\n"
            f"       Add <!-- BEGIN: {missing[0]} --> ... <!-- END: {missing[0]} --> to COURSE_PROFILE.md"
        )
    out = PLACEHOLDER_RE.sub(lambda m: blocks[m.group(1)], skel)
    leftover = PLACEHOLDER_RE.findall(out)
    if leftover:  # a block's own text contained a placeholder
        sys.exit(f"ERROR: {skel_name} still has unsubstituted {set(leftover)} after rendering")
    return out, needed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("course", help="course folder name, e.g. operating-systems")
    ap.add_argument("--check", action="store_true",
                    help="verify rendered files are up to date; write nothing")
    args = ap.parse_args()

    course_dir = HERE / args.course
    if not course_dir.is_dir():
        sys.exit(f"ERROR: no such course folder: {course_dir}")

    blocks = load_profile(course_dir)
    out_dir = course_dir / "rendered"
    if not args.check:
        out_dir.mkdir(exist_ok=True)

    used, stale = set(), []
    for skel_name, out_name in SKELETONS.items():
        rendered, needed = render_one(skel_name, blocks)
        used |= needed
        target = out_dir / out_name
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != rendered:
                stale.append(out_name)
        else:
            target.write_text(rendered, encoding="utf-8")
            print(f"  {out_name:28} <- {skel_name}")

    # Provenance as a sibling file, so the prompts themselves stay pasteable.
    readme = README.format(
        course=args.course,
        table="\n".join(f"| `{out}` | `_shared/{skel}` |" for skel, out in SKELETONS.items()),
    )
    readme_path = out_dir / "README.md"
    if args.check:
        if not readme_path.exists() or readme_path.read_text(encoding="utf-8") != readme:
            stale.append("README.md")
    else:
        readme_path.write_text(readme, encoding="utf-8")

    unused = sorted(set(blocks) - used)
    if unused:
        print(f"\nWARNING: profile defines unused block(s): {unused}", file=sys.stderr)

    if args.check:
        if stale:
            sys.exit(f"STALE (re-run render.py): {stale}")
        print(f"[ok] {args.course}: rendered prompts are up to date")
    else:
        print(f"\n[done] {args.course} -> {out_dir}")
        print("Course staff must review rendered/ before the course opens.")


if __name__ == "__main__":
    main()
