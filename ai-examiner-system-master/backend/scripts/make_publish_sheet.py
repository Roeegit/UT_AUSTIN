#!/usr/bin/env python3
"""
make_publish_sheet.py — Build the student-facing publish CSV from a grading run.

Reads the code-review grading results (<assignment>_results.jsonl) and writes a
clean sheet you can publish to students, keyed by their canonical 9-digit ID:

    student_id, grade, feedback

  • Only status=="graded" rows are included. Non-submitters (no_repo / no_submission)
    are left out — they get 0 in the gradebook by default.
  • feedback = the Hebrew student-facing review ONLY. Staff-only fields
    (codeReviewNotes, signalB_*) are never included.
  • A --factor / --add curve can be applied here (identity by default) so you can
    publish final grades without re-running the grader.

Full 9-digit IDs are resolved from the local roster/mapping files:
    private-data/student_emails.csv          (full_id, email, group)
    private-data/groupai_students-v2.csv     (Student ID, Email)
    private-data/groupnotai_students-v2.csv  (Student ID, Email)
Resolution order per student:
    1. id.txt already held a 9-digit ID   (row student_id)
    2. email match (classroom email -> full_id)
    3. last-5 match (id.txt last-5 -> full_id), only if unambiguous among enrolled
Anything unresolved is PRINTED and left out of the sheet, so you fix it by hand
rather than publish a wrong/blank key.

Run from backend/:
  python scripts/make_publish_sheet.py
  python scripts/make_publish_sheet.py --add 5           # +5 to every grade (cap 100)
  python scripts/make_publish_sheet.py --mult 1.05       # multiply grades by 1.05 (cap 100)
"""

import argparse
import csv
import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PRIVATE = _BACKEND_DIR.parent / "private-data"


# ──────────────────────────────────────────────────────────────────────────────
# Build email->full_id and last5->{full_ids} from the local mapping files
# ──────────────────────────────────────────────────────────────────────────────

def _add_pair(email2id, last5map, full_id, email):
    full_id = (full_id or "").strip()
    if len(full_id) != 9 or not full_id.isdigit():
        return
    email = (email or "").strip().lower()
    if email:
        email2id.setdefault(email, full_id)
    last5map.setdefault(full_id[-5:], set()).add(full_id)


def load_id_maps() -> tuple[dict[str, str], dict[str, set[str]]]:
    email2id: dict[str, str] = {}
    last5map: dict[str, set[str]] = {}

    sources = [
        (_PRIVATE / "student_emails.csv", "full_id", "email"),
        (_PRIVATE / "groupai_students-v2.csv", "Student ID", "Email"),
        (_PRIVATE / "groupnotai_students-v2.csv", "Student ID", "Email"),
    ]
    for path, id_col, email_col in sources:
        if not path.exists():
            print(f"[warn] mapping file missing: {path}")
            continue
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                _add_pair(email2id, last5map, row.get(id_col), row.get(email_col))
    print(f"[maps] {len(email2id)} emails, {len(last5map)} distinct last-5 keys loaded.")
    return email2id, last5map


def resolve_full_id(row: dict, email2id, last5map) -> tuple[str | None, str]:
    """Return (full_9_digit_id or None, how) for a graded row."""
    sid = (row.get("student_id") or "").strip()
    if len(sid) == 9 and sid.isdigit():
        return sid, "id.txt-9"

    email = (row.get("email") or "").strip().lower()
    if email and email in email2id:
        return email2id[email], "email"

    last5 = (row.get("student_id_5") or "").strip()
    if len(last5) == 5 and last5.isdigit():
        candidates = last5map.get(last5, set())
        if len(candidates) == 1:
            return next(iter(candidates)), "last5"
        if len(candidates) > 1:
            return None, f"ambiguous-last5({len(candidates)})"
    return None, "unresolved"


# ──────────────────────────────────────────────────────────────────────────────
# Grade curve
# ──────────────────────────────────────────────────────────────────────────────

def apply_curve(grade, mult: float, add: float, cap: int) -> int:
    return int(round(min(cap, float(grade) * mult + add)))


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assignment", default="assignment-4")
    ap.add_argument("--out-dir", default=None, help="grading dir (default: private-data/<assignment>_grading)")
    ap.add_argument("--mult", type=float, default=1.0, help="multiply each grade by this (default 1.0)")
    ap.add_argument("--add", type=float, default=0.0, help="add this many points after multiplying (default 0)")
    ap.add_argument("--cap", type=int, default=100, help="grade ceiling (default 100)")
    ap.add_argument("--bump-to-100", type=int, default=None, help="grades >= this value become 100 (e.g. --bump-to-100 97)")
    ap.add_argument("--exclude-below", type=int, default=None, help="drop graded students whose raw score is < this from the sheet, treating them as non-submissions/0 (e.g. --exclude-below 10 removes the unmodified-stub 5s)")
    ap.add_argument("--unresolved-as-username", action="store_true", help="instead of dropping students whose 9-digit ID couldn't be resolved, publish them with their github username as the student_id placeholder (fix on appeal)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else (_PRIVATE / f"{args.assignment}_grading")
    results_path = out_dir / f"{args.assignment}_results.jsonl"
    publish_path = out_dir / f"{args.assignment}_publish.csv"
    if not results_path.exists():
        sys.exit(f"[FATAL] results file not found: {results_path}\nRun the grader first.")

    rows = [json.loads(l) for l in results_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    email2id, last5map = load_id_maps()

    graded = [r for r in rows if r.get("status") == "graded"]
    excluded = [r for r in rows if r.get("status") != "graded"]

    publish_rows: list[tuple[str, int, str]] = []
    unresolved: list[dict] = []
    excluded_low: list[dict] = []   # graded but below --exclude-below → treated as non-submission
    seen_ids: dict[str, str] = {}   # full_id -> github_username (collision guard)

    placeholder: list[dict] = []    # unresolved but published under github username (--unresolved-as-username)

    def _final_grade(r) -> int:
        grade = apply_curve(r.get("staticCodeQualityScore", 0), args.mult, args.add, args.cap)
        if args.bump_to_100 is not None and grade >= args.bump_to_100:
            grade = 100
        return grade

    for r in graded:
        raw = int(r.get("staticCodeQualityScore") or 0)
        if args.exclude_below is not None and raw < args.exclude_below:
            excluded_low.append(r)
            continue
        full_id, how = resolve_full_id(r, email2id, last5map)
        why = None
        if not full_id:
            why = how
        elif full_id in seen_ids and seen_ids[full_id] != r.get("github_username"):
            why = f"duplicate-id (also {seen_ids[full_id]})"
        if why:
            r["_why"] = why
            if args.unresolved_as_username:
                placeholder.append(r)
                publish_rows.append((r.get("github_username"), _final_grade(r),
                                     r.get("studentStaticFeedback") or ""))
            else:
                unresolved.append(r)
            continue
        seen_ids[full_id] = r.get("github_username")
        publish_rows.append((full_id, _final_grade(r), r.get("studentStaticFeedback") or ""))

    publish_rows.sort(key=lambda x: x[0])
    with publish_path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["student_id", "grade", "feedback"])
        w.writerows(publish_rows)

    curve = "identity" if (args.mult == 1.0 and args.add == 0.0) else f"grade*{args.mult}+{args.add} (cap {args.cap})"
    if args.bump_to_100 is not None:
        curve += f" ; grades >= {args.bump_to_100} -> 100"
    print()
    print(f"Curve applied         : {curve}")
    print(f"Graded rows           : {len(graded)}")
    print(f"  -> published        : {len(publish_rows)}")
    print(f"  -> could not resolve : {len(unresolved)}")
    if placeholder:
        ph = ", ".join("{}={}".format(r["github_username"], _final_grade(r)) for r in placeholder)
        print(f"  -> published w/ username as id (fix on appeal): {len(placeholder)}  [{ph}]")
    if args.exclude_below is not None:
        print(f"  -> excluded (score < {args.exclude_below}) : {len(excluded_low)}  " +
              ("[" + ", ".join(r['github_username'] for r in excluded_low) + "]" if excluded_low else ""))
    print(f"Excluded (get 0)      : {len(excluded) + len(excluded_low)}  (no_repo / no_submission / error" +
          (f" / score<{args.exclude_below}" if args.exclude_below is not None else "") + ")")
    print(f"\n[OK] Publish sheet: {publish_path}")

    if unresolved:
        print("\n[WARNING] Could NOT resolve a 9-digit ID for these graded students - fix by hand:")
        for r in unresolved:
            print(f"    {r.get('github_username'):<24} "
                  f"id.txt5={r.get('student_id_5') or '-':<6} "
                  f"email={r.get('email') or '-':<32} grade={r.get('staticCodeQualityScore')} "
                  f"[{r.get('_why')}]")


if __name__ == "__main__":
    main()
