#!/usr/bin/env python3
"""
grade_assignment_code_review.py — Code-review-only batch grader.

For an assignment where students DO NOT sit an oral exam (e.g. assignment 4),
this fetches every student's repo straight from GitHub (in-memory; no GCS) and
runs ONLY the Code Reviewer agent on it — concurrently across students. It needs
ONLY ANTHROPIC_API_KEY + the GITHUB_APP_* vars (no Google credentials at all).

Outputs (to private-data/<assignment>_grading/):
  1. <assignment>_full.csv    — every interesting field: score, Signal-B AI-authorship
                                signal, reviewer notes, model used, fetch status,
                                files found/missing, last_updated, (updated_after_deadline).
                                Keep this for the archive; we may mine it later.
  2. <assignment>_grades.csv  — clean publish sheet: student_id, name, email,
                                github_username, grade, last_updated. grade = staticCodeQualityScore.
  3. <assignment>_summary.txt — count / mean / std / median / min / max of the grades,
                                plus (if --deadline given) how many students pushed late.

It checkpoints to a .jsonl as it goes, so a crash or rate-limit mid-run loses
nothing.

Usage:
  python scripts/grade_assignment_code_review.py                 # fresh full run (assignment-4)
  python scripts/grade_assignment_code_review.py --limit 5       # smoke test on 5 students
  python scripts/grade_assignment_code_review.py --resume        # continue an interrupted run
  python scripts/grade_assignment_code_review.py \
        --deadline 2026-06-30T23:59:59                            # flag/count students who pushed late
  python scripts/grade_assignment_code_review.py --regrade-updated
        # reuse a previous run; re-grade ONLY students whose repo changed since then

Before running you MUST replace the two placeholders (the script refuses otherwise):
  • backend/assignments/assignment-4_readme.md   — the real spec
  • backend/assignments/assignment-4_files.json  — the real submitted-file list
"""

import argparse
import base64
import csv
import json
import os
import random
import re
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# ── Make backend/ importable and load .env ───────────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(_BACKEND_DIR / ".env")

import anthropic
import jwt          # PyJWT[cryptography]
import requests

import config
from agents import call_code_reviewer
from roster_utils import load_classroom_roster   # uses the LOCAL roster csv (no GCS bucket set)

# Administrative files we fetch (for identity) but never show the code reviewer.
_HIDDEN_FROM_REVIEWER = {"id.txt"}

# ──────────────────────────────────────────────────────────────────────────────
# GitHub App auth + read-only repo access (self-contained; no GCS, mirrors
# github_stub's logic but without that module's import-time GCS client).
# ──────────────────────────────────────────────────────────────────────────────

_GH_API = "https://api.github.com"
_GH_ORG = os.environ.get("GITHUB_ORG", "")
_GH_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
_GH_SUBFOLDER = os.environ.get("GITHUB_FILES_PATH", "").strip("/")


def _gh_private_key() -> str:
    pem = os.environ.get("GITHUB_PRIVATE_KEY", "")
    if pem:
        return pem.replace("\\n", "\n")
    path = os.environ.get("GITHUB_PRIVATE_KEY_PATH", "")
    if path:
        return Path(path).read_text(encoding="utf-8")
    raise RuntimeError("Set GITHUB_PRIVATE_KEY or GITHUB_PRIVATE_KEY_PATH in backend/.env")


def _gh_app_jwt() -> str:
    app_id = os.environ.get("GITHUB_APP_ID", "")
    if not app_id:
        raise RuntimeError("GITHUB_APP_ID not set")
    now = int(time.time())
    return jwt.encode({"iat": now - 60, "exp": now + 5 * 60, "iss": app_id},
                      _gh_private_key(), algorithm="RS256")


def _gh_installation_token() -> str:
    inst = os.environ.get("GITHUB_INSTALLATION_ID", "")
    if not inst:
        raise RuntimeError("GITHUB_INSTALLATION_ID not set")
    r = requests.post(
        f"{_GH_API}/app/installations/{inst}/access_tokens",
        headers={"Authorization": f"Bearer {_gh_app_jwt()}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
        timeout=15,
    )
    if not r.ok:
        raise RuntimeError(f"installation token failed: HTTP {r.status_code} — {r.text[:200]}")
    return r.json()["token"]


def _gh_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def _gh_get(url: str, token: str, params: dict | None = None, attempts: int = 6):
    """
    GET with retry/backoff on GitHub throttling. 200 and 404 return immediately
    (404 = legitimately absent). 403 (incl. secondary rate limit), 429, and 5xx
    are retried, honoring Retry-After / x-ratelimit-reset. Returns the last
    response; a persistent non-200/404 is the caller's signal to raise, so a
    throttled fetch is NEVER silently treated as "missing".
    """
    headers = _gh_headers(token)
    last = None
    for attempt in range(attempts):
        try:
            last = requests.get(url, headers=headers, params=params, timeout=20)
        except requests.RequestException:
            time.sleep(min(2 ** attempt, 30))
            continue
        if last.status_code in (200, 404):
            return last
        if last.status_code == 403 or last.status_code == 429 or last.status_code >= 500:
            retry_after = last.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = int(retry_after)
            elif last.headers.get("x-ratelimit-remaining") == "0":
                reset = last.headers.get("x-ratelimit-reset")
                wait = max(0, int(reset) - int(time.time())) + 1 if reset and reset.isdigit() else 60
            else:
                wait = min(2 ** attempt, 30)
            time.sleep(min(wait, 90) + random.uniform(0, 1))
            continue
        return last  # other 4xx — let caller decide
    return last


def resolve_repo(base_name: str, token: str) -> tuple[str | None, str]:
    """
    Resolve the student's repo, tolerating GitHub Classroom re-accept suffixes
    (-1..-5). Returns (owner/repo or None if no variant exists, pushed_at ISO8601).
    Probes are sequential (not a nested thread pool) to avoid tripping GitHub's
    secondary rate limit under outer concurrency.
    """
    if not _GH_ORG:
        raise RuntimeError("GITHUB_ORG not set")
    candidates = [base_name] + [f"{base_name}-{i}" for i in range(1, 6)]
    best_name, best_pushed = None, ""
    for name in candidates:
        r = _gh_get(f"{_GH_API}/repos/{_GH_ORG}/{name}", token)
        if r is not None and r.status_code == 200:
            pushed = r.json().get("pushed_at", "")
            if pushed and pushed > best_pushed:
                best_pushed, best_name = pushed, name
        elif r is not None and r.status_code not in (200, 404):
            # persistent throttle/error on a probe — surface rather than guess "no repo"
            raise RuntimeError(f"repo probe {name}: HTTP {r.status_code}")
    if best_name is None:
        return None, ""
    return f"{_GH_ORG}/{best_name}", best_pushed


def fetch_file(repo_full: str, filename: str, token: str) -> str | None:
    """Return file text, None on genuine 404, or raise on a persistent fetch error."""
    in_path = f"{_GH_SUBFOLDER}/{filename}" if _GH_SUBFOLDER else filename
    r = _gh_get(f"{_GH_API}/repos/{repo_full}/contents/{in_path}", token, params={"ref": _GH_BRANCH})
    if r is None:
        raise RuntimeError(f"fetch {filename}: no response")
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise RuntimeError(f"fetch {filename}: HTTP {r.status_code}")
    data = r.json()
    if data.get("encoding") != "base64":
        raise RuntimeError(f"fetch {filename}: unexpected encoding {data.get('encoding')}")
    return base64.b64decode(data["content"]).decode("utf-8", errors="replace").strip()


class TokenProvider:
    """Installation tokens last ~1h; refresh well before that for long runs."""
    _REFRESH_AFTER = 45 * 60

    def __init__(self):
        self._lock = threading.Lock()
        self._token = None
        self._issued_at = 0.0

    def get(self) -> str:
        with self._lock:
            if self._token is None or (time.time() - self._issued_at) > self._REFRESH_AFTER:
                self._token = _gh_installation_token()
                self._issued_at = time.time()
            return self._token


# ──────────────────────────────────────────────────────────────────────────────
# Inputs: README + file list (validated, refuses placeholders)
# ──────────────────────────────────────────────────────────────────────────────

def load_assignment_inputs(assignment: str) -> tuple[str, list[str]]:
    assign_dir = _BACKEND_DIR / "assignments"
    readme_path = assign_dir / f"{assignment}_readme.md"
    files_path = assign_dir / f"{assignment}_files.json"

    if not readme_path.exists():
        sys.exit(f"[FATAL] Missing README: {readme_path}")
    readme = readme_path.read_text(encoding="utf-8")
    if "PLACEHOLDER_README" in readme:
        sys.exit(f"[FATAL] {readme_path} is still the placeholder — paste the real spec first.")

    if not files_path.exists():
        sys.exit(f"[FATAL] Missing file list: {files_path}")
    files_doc = json.loads(files_path.read_text(encoding="utf-8"))
    if files_doc.get("_placeholder"):
        sys.exit(f"[FATAL] {files_path} is still the placeholder — set the real file list first.")
    files = files_doc.get("files") or []
    if not files:
        sys.exit(f"[FATAL] {files_path} has an empty 'files' list.")
    return readme, files


def load_code_reviewer_prompt() -> str:
    return Path(config.CODE_REVIEWER_PROMPT_PATH).read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# Time helpers (last_updated vs deadline)
# ──────────────────────────────────────────────────────────────────────────────

def _parse_pushed(s: str | None) -> datetime | None:
    """Parse GitHub pushed_at ('...Z') into an aware UTC datetime."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_deadline(s: str) -> datetime:
    """Parse --deadline. A naive value is interpreted as Asia/Jerusalem (course tz)."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        from zoneinfo import ZoneInfo
        dt = dt.replace(tzinfo=ZoneInfo("Asia/Jerusalem"))
    return dt


# ──────────────────────────────────────────────────────────────────────────────
# Per-student id parsing + worker
# ──────────────────────────────────────────────────────────────────────────────

def _parse_id(content: str | None) -> tuple[str | None, str | None]:
    """Return (full_9_digit, last5) parsed from id.txt content (best effort)."""
    if not content:
        return None, None
    digits = re.sub(r"\D", "", content)
    if len(digits) == 9:
        return digits, digits[-5:]
    if len(digits) == 5:
        return None, digits
    return None, None


def _blank_row(entry) -> dict:
    return {
        "github_username": entry.github_username,
        "name": entry.full_name_he,
        "email": entry.email,
        "student_id": "",
        "student_id_5": "",
        "repo": "",
        "status": "",                 # graded | no_submission | no_repo | error
        "last_updated": "",           # repo pushed_at (ISO8601 UTC)
        "updated_after_deadline": "",
        "files_found": "",
        "files_missing": "",
        "staticCodeQualityScore": "",
        "signalB_level": "",
        "signalB_markers": "",
        "signalB_analysis": "",
        "codeReviewNotes": "",
        "studentStaticFeedback": "",   # Hebrew, student-facing — safe to email to the student
        "model_used": "",
        "error": "",
        "reused": False,              # internal: True when copied from a prior run (not in CSV)
    }


def _apply_resolution(row: dict, repo_full: str | None, pushed_at: str, deadline_dt) -> None:
    """Fill the resolution-derived fields (repo, last_updated, updated_after_deadline)."""
    row["repo"] = repo_full or ""
    row["last_updated"] = pushed_at
    if deadline_dt and pushed_at:
        pd = _parse_pushed(pushed_at)
        row["updated_after_deadline"] = bool(pd and pd > deadline_dt)


def resolve_all(students, assignment, token_provider, workers) -> dict[str, tuple[str | None, str]]:
    """
    Cheap pass (no LLM): resolve every student's repo + pushed_at concurrently.
    Returns {github_username: (owner/repo or None, pushed_at)}.
    """
    out: dict[str, tuple[str | None, str]] = {}

    def _one(e):
        tok = token_provider.get()
        return e.github_username, resolve_repo(f"{assignment}-{e.github_username}", tok)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for uname, res in pool.map(_one, students):
            out[uname] = res
    return out


def grade_one_student(
    entry, repo_full, pushed_at, files, token_provider, client, reviewer_prompt, readme, deadline_dt,
) -> dict:
    """Fetch + review one student (repo already resolved). Never raises."""
    row = _blank_row(entry)
    _apply_resolution(row, repo_full, pushed_at, deadline_dt)
    try:
        token = token_provider.get()
        found, missing = {}, []
        for f in files:
            content = fetch_file(repo_full, f, token)
            if content is not None:
                found[f] = content
            else:
                missing.append(f)
        row["files_found"] = ";".join(sorted(found))
        row["files_missing"] = ";".join(missing)

        full_id, last5 = _parse_id(found.get("id.txt"))
        row["student_id"] = full_id or ""
        row["student_id_5"] = last5 or ""

        reviewer_files = {
            f: (found.get(f) or "[NOT SUBMITTED]")
            for f in files if f not in _HIDDEN_FROM_REVIEWER
        }
        code_present = any(found.get(f) for f in files if f not in _HIDDEN_FROM_REVIEWER)
        if not code_present:
            row["status"] = "no_submission"
            return row

        review, model_used = call_code_reviewer(client, reviewer_prompt, readme, reviewer_files)
        sigb = review.get("signalBAssessment", {}) or {}
        row["status"] = "graded"
        row["staticCodeQualityScore"] = review.get("staticCodeQualityScore", "")
        row["signalB_level"] = sigb.get("level", "")
        row["signalB_markers"] = sigb.get("markersFound", "")
        row["signalB_analysis"] = sigb.get("analysis", "")
        row["codeReviewNotes"] = review.get("codeReviewNotes", "")
        row["studentStaticFeedback"] = review.get("studentStaticFeedback", "")
        row["model_used"] = model_used
        return row
    except Exception as exc:  # noqa: BLE001 — one bad student must not sink the run
        row["status"] = "error"
        row["error"] = f"{type(exc).__name__}: {exc}"[:500]
        return row


# ──────────────────────────────────────────────────────────────────────────────
# Output writers
# ──────────────────────────────────────────────────────────────────────────────

_FULL_FIELDS = [
    "github_username", "name", "email", "student_id", "student_id_5", "repo",
    "status", "last_updated", "updated_after_deadline", "files_found", "files_missing",
    "staticCodeQualityScore", "signalB_level", "signalB_markers", "signalB_analysis",
    "codeReviewNotes", "studentStaticFeedback", "model_used", "error",
]


def write_full_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=_FULL_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: x["github_username"].lower()):
            w.writerow(r)


def write_publish_csv(rows: list[dict], path: Path) -> None:
    fields = ["student_id", "name", "email", "github_username", "grade", "last_updated"]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x.get("name") or "").strip()):
            if r["status"] != "graded":
                continue
            w.writerow({
                "student_id": r["student_id"] or r["student_id_5"],
                "name": r["name"],
                "email": r["email"],
                "github_username": r["github_username"],
                "grade": r["staticCodeQualityScore"],
                "last_updated": r["last_updated"],
            })


def write_summary(rows: list[dict], path: Path, deadline_dt, regrade_updated: bool) -> str:
    grades = [float(r["staticCodeQualityScore"]) for r in rows
              if r["status"] == "graded" and r["staticCodeQualityScore"] != ""]
    n_graded = len(grades)
    counts = {k: sum(1 for r in rows if r["status"] == k)
              for k in ("graded", "no_submission", "no_repo", "error")}

    lines = [
        "Assignment code-review grading summary",
        "=" * 40,
        f"Roster students processed : {len(rows)}",
        f"Graded (have a grade)     : {counts['graded']}",
        f"No code submitted         : {counts['no_submission']}",
        f"No repo found             : {counts['no_repo']}",
        f"Errors (need manual look) : {counts['error']}",
    ]
    if regrade_updated:
        lines.append(f"Reused (repo unchanged)   : {sum(1 for r in rows if r.get('reused'))}")
        lines.append(f"Re-graded (repo changed)  : {sum(1 for r in rows if r['status'] == 'graded' and not r.get('reused'))}")
    lines.append("")

    if n_graded:
        lines += [
            f"Grade statistics (over the {n_graded} graded students):",
            f"  mean   : {statistics.mean(grades):.2f}",
            f"  std    : {statistics.stdev(grades) if n_graded > 1 else 0.0:.2f}   (sample / n-1)",
            f"  std    : {statistics.pstdev(grades):.2f}   (population / n)",
            f"  median : {statistics.median(grades):.2f}",
            f"  min    : {min(grades):.0f}",
            f"  max    : {max(grades):.0f}",
        ]
    else:
        lines.append("No graded students — nothing to summarize.")

    if deadline_dt:
        late = [r for r in rows if r["updated_after_deadline"] is True]
        lines += [
            "",
            f"Repos pushed AFTER the deadline ({deadline_dt.isoformat()}): {len(late)}",
            "  -> Review these for manual approve/reject (last_updated column shows when).",
        ]
        for r in sorted(late, key=lambda x: x["last_updated"], reverse=True):
            lines.append(f"    {r['last_updated']}  {r['github_username']:<24} status={r['status']}")

    if counts["error"]:
        lines += ["", "Students with errors:"]
        lines += [f"  {r['github_username']}: {r['error']}" for r in rows if r["status"] == "error"]

    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")
    return text


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assignment", default="assignment-4", help="assignment name / repo prefix (default: assignment-4)")
    ap.add_argument("--workers", type=int, default=6, help="concurrent students (default: 6)")
    ap.add_argument("--limit", type=int, default=0, help="grade only the first N roster students (smoke test)")
    ap.add_argument("--out-dir", default=None, help="output dir (default: private-data/<assignment>_grading)")
    ap.add_argument("--deadline", default=None, help="ISO datetime; flag/count students who pushed after it (naive = Asia/Jerusalem)")
    ap.add_argument("--resume", action="store_true", help="continue an interrupted run: skip students already in the checkpoint")
    ap.add_argument("--regrade-updated", action="store_true", help="reuse a previous run; re-grade ONLY students whose repo changed since")
    ap.add_argument("--yes", "-y", action="store_true", help="skip the confirmation prompt (for --regrade-updated)")
    args = ap.parse_args()

    if args.resume and args.regrade_updated:
        sys.exit("[FATAL] --resume and --regrade-updated are mutually exclusive.")

    readme, files = load_assignment_inputs(args.assignment)
    reviewer_prompt = load_code_reviewer_prompt()
    deadline_dt = parse_deadline(args.deadline) if args.deadline else None

    out_dir = Path(args.out_dir) if args.out_dir else (_BACKEND_DIR.parent / "private-data" / f"{args.assignment}_grading")
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = out_dir / f"{args.assignment}_results.jsonl"
    full_csv = out_dir / f"{args.assignment}_full.csv"
    publish_csv = out_dir / f"{args.assignment}_grades.csv"
    summary_txt = out_dir / f"{args.assignment}_summary.txt"

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("[FATAL] ANTHROPIC_API_KEY not set (check backend/.env).")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    roster = load_classroom_roster()
    students = sorted(roster.values(), key=lambda e: e.github_username.lower())
    if args.limit:
        students = students[: args.limit]

    # Load any prior results — but do NOT touch the checkpoint yet. For a regrade we
    # wait until you confirm before mutating anything.
    prior: dict[str, dict] = {}     # username -> prior row (for --regrade-updated)
    done: dict[str, dict] = {}      # username -> row to keep as-is and skip (for --resume)

    if args.regrade_updated:
        if not checkpoint.exists():
            sys.exit(f"[FATAL] --regrade-updated needs a previous run, but {checkpoint} is missing.")
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                prior[r["github_username"]] = r
        print(f"[regrade] loaded {len(prior)} prior results.")
    elif args.resume and checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["github_username"]] = r
        print(f"[resume] {len(done)} students already in checkpoint — skipping them.")

    todo = [e for e in students if e.github_username not in done]
    print(f"[*] Assignment   : {args.assignment}")
    print(f"[*] Files fetched: {files}")
    if deadline_dt:
        print(f"[*] Deadline     : {deadline_dt.isoformat()}  (flag late pushes)")
    print(f"[*] Roster       : {len(students)} students  ({len(todo)} to process, {len(done)} resumed)")
    print(f"[*] Workers      : {args.workers}")
    print(f"[*] Output dir   : {out_dir}")
    print()

    token_provider = TokenProvider()

    # ── Resolution pass (cheap: GitHub only, no LLM) ─────────────────────────
    print(f"[*] Resolving {len(todo)} repos (last_updated / pushed_at)...")
    resolved = resolve_all(todo, args.assignment, token_provider, args.workers)

    def _action(e) -> str:
        repo_full, pushed_at = resolved[e.github_username]
        if repo_full is None:
            return "no_repo"
        if args.regrade_updated:
            p = prior.get(e.github_username)
            if p and p.get("status") == "graded" and pushed_at and p.get("last_updated") == pushed_at:
                return "reuse"
        return "grade"

    actions = {e.github_username: _action(e) for e in todo}
    to_grade = [e for e in todo if actions[e.github_username] == "grade"]
    n_reuse = sum(1 for a in actions.values() if a == "reuse")
    n_no_repo = sum(1 for a in actions.values() if a == "no_repo")

    # ── Confirm before spending LLM calls on a regrade ───────────────────────
    if args.regrade_updated:
        changed = [e for e in to_grade
                   if prior.get(e.github_username, {}).get("status") == "graded"]
        new_or_ungraded = [e for e in to_grade if e not in changed]
        print()
        print(f"  Repos changed since last run : {len(changed)}")
        print(f"  New / not-yet-graded         : {len(new_or_ungraded)}")
        print(f"  Unchanged (will reuse)       : {n_reuse}")
        print(f"  No repo found                : {n_no_repo}")
        if not to_grade:
            print("\nNothing to regrade — every repo is unchanged. Exiting (no changes made).")
            return
        if not args.yes:
            extra = f" (+{len(new_or_ungraded)} new/ungraded)" if new_or_ungraded else ""
            try:
                resp = input(f"\nThere are {len(changed)} students with updated GitHubs{extra}. "
                             f"Proceed with regrading {len(to_grade)}? [y/N] ")
            except EOFError:
                resp = ""
            if resp.strip().lower() not in ("y", "yes"):
                print("Aborted - no changes made (prior results untouched).")
                return

    # ── Now it's safe to mutate the checkpoint ───────────────────────────────
    if args.regrade_updated:
        backup = checkpoint.with_suffix(".jsonl.prev")
        checkpoint.replace(backup)   # preserve the prior run; write a fresh checkpoint
        print(f"[regrade] prior checkpoint backed up to {backup.name}.")
    elif not args.resume and checkpoint.exists():
        backup = checkpoint.with_suffix(".jsonl.prev")
        checkpoint.replace(backup)   # fresh run: keep the old checkpoint as .prev
        print(f"[fresh] previous checkpoint backed up to {backup.name}; starting clean.")

    results: list[dict] = list(done.values())
    ckpt_lock = threading.Lock()

    def _checkpoint(row: dict) -> None:
        with ckpt_lock:
            with checkpoint.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Emit the rows that need no LLM call (reuse / no_repo) straight to results+checkpoint.
    for e in todo:
        a = actions[e.github_username]
        if a == "grade":
            continue
        repo_full, pushed_at = resolved[e.github_username]
        if a == "reuse":
            row = dict(prior[e.github_username])
            row["reused"] = True
            _apply_resolution(row, repo_full, pushed_at, deadline_dt)
        else:  # no_repo
            row = _blank_row(e)
            _apply_resolution(row, repo_full, pushed_at, deadline_dt)
            row["status"] = "no_repo"
        results.append(row)
        _checkpoint(row)

    # ── Grade the rest (the expensive LLM pass) ──────────────────────────────
    completed, total = 0, len(to_grade)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                grade_one_student, e, *resolved[e.github_username], files, token_provider,
                client, reviewer_prompt, readme, deadline_dt,
            ): e
            for e in to_grade
        }
        for fut in as_completed(futures):
            row = fut.result()
            results.append(row)
            _checkpoint(row)
            completed += 1
            score = row.get("staticCodeQualityScore", "")
            tag = f"grade={score}" if row["status"] == "graded" else row["status"]
            print(f"  [{completed:>4}/{total}] {row['github_username']:<24} {tag}")

    write_full_csv(results, full_csv)
    write_publish_csv(results, publish_csv)
    summary = write_summary(results, summary_txt, deadline_dt, args.regrade_updated)

    print()
    print(summary)
    print(f"[OK] Full csv    : {full_csv}")
    print(f"[OK] Publish csv : {publish_csv}")
    print(f"[OK] Summary     : {summary_txt}")
    print(f"[i] Checkpoint  : {checkpoint}  (--resume to continue, --regrade-updated to refresh changed repos)")


if __name__ == "__main__":
    main()
