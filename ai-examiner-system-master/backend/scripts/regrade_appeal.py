"""
regrade_appeal.py — Re-run the grader for a single student with an appeal note injected.

Usage (run from backend/):
    python scripts/regrade_appeal.py --username CoralSudayBiu --assignment biu-os-2026-assignment-1-claude-code-shell-hooks

The script:
  1. Downloads the student's result blob from GCS.
  2. Calls call_grader with APPEAL_NOTE prepended to extra_notes.
  3. Recomputes the final grade.
  4. Uploads the updated blob back to GCS.
  5. Does NOT mark grade_email_sent — the caller should send the email separately.

Dry-run (print new verdict without writing):
    python scripts/regrade_appeal.py --username CoralSudayBiu --assignment biu-os-2026-assignment-1-claude-code-shell-hooks --dry-run
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import subprocess
import tempfile

import anthropic

from agents import call_grader, compute_final_grade

_GCLOUD = "gcloud.cmd" if sys.platform == "win32" else "gcloud"


def _gcs_download(gs_path: str) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    subprocess.run([_GCLOUD, "storage", "cp", gs_path, tmp], check=True,
                   capture_output=True)
    with open(tmp, encoding="utf-8-sig") as f:
        data = json.load(f)
    os.unlink(tmp)
    return data


def _gcs_upload(data: dict, gs_path: str) -> None:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False,
                                     mode="w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        tmp = f.name
    subprocess.run([_GCLOUD, "storage", "cp", tmp, gs_path,
                    "--content-type=application/json; charset=utf-8"],
                   check=True, capture_output=True)
    os.unlink(tmp)

# ---------------------------------------------------------------------------
# Appeal note — injected as extra_notes into the grader prompt
# ---------------------------------------------------------------------------

# Change for a different student with different appeal
APPEAL_NOTE = """\
STAFF NOTE — ACCEPTED APPEAL:
During Q1, the student typed the regex pattern as "(feat|fix)^" with the "^" anchor \
appearing at the end of the expression. After reviewing the appeal, the course staff \
has accepted that this was caused by a known RTL/Hebrew ↔ English text-direction \
formatting issue in the exam interface: when the student switched from Hebrew to \
English mid-sentence, the Unicode bidirectional algorithm placed the "^" character \
at the visually opposite end of the expression.
The student's conceptual intent — to anchor the match to the start of the string — \
was correct, and the rest of the Q1 answer (exit code 2, suggestion mechanism, \
overall behavior) was accurate.
For the purpose of this grading, please treat the Q1 regex answer as if the "^" \
was correctly placed at the beginning: "^(feat|fix)". Evaluate Q1 accordingly.
"""


def run(username: str, assignment: str, dry_run: bool) -> None:
    bucket_name = os.environ.get("GCS_SUBMISSIONS_BUCKET", "").strip()
    if not bucket_name:
        print("ERROR: GCS_SUBMISSIONS_BUCKET not set.", file=sys.stderr)
        sys.exit(1)

    # ── Load blob ──────────────────────────────────────────────────────────
    blob_path = f"results/{assignment}/{username}.json"
    gs_uri = f"gs://{bucket_name}/{blob_path}"
    print(f"Loading blob: {gs_uri}")
    blob_data = _gcs_download(gs_uri)

    transcript = blob_data.get("transcript", [])
    if isinstance(transcript, str):
        transcript = json.loads(transcript)

    signal_b = (blob_data.get("code_review") or {}).get("signalBAssessment", {})
    static_score = (blob_data.get("final_grade") or {}).get("staticCodeQualityScore")

    # ── Load grader prompt + README ────────────────────────────────────────
    base = Path(__file__).parent.parent
    grader_prompt = (base / "prompts" / "grader_prompt.txt").read_text(encoding="utf-8")
    readme_path = base / "assignments" / f"{assignment}_readme.md"
    if not readme_path.exists():
        print(f"ERROR: README not found at {readme_path}", file=sys.stderr)
        sys.exit(1)
    assignment_readme = readme_path.read_text(encoding="utf-8")

    # ── Call grader ────────────────────────────────────────────────────────
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    print("Calling grader...")
    grader_json, model_used = call_grader(
        client,
        grader_prompt,
        assignment_readme,
        signal_b,
        transcript,
        extra_notes=APPEAL_NOTE,
    )
    print(f"Grader model: {model_used}")

    new_oral   = grader_json.get("oralDefenseScore")
    new_final  = compute_final_grade(new_oral, static_score)
    old_oral   = (blob_data.get("final_grade") or {}).get("oralDefenseScore")
    old_final  = (blob_data.get("final_grade") or {}).get("finalWeightedGrade")

    print(f"\nOld oral={old_oral}  new oral={new_oral}")
    print(f"Old finalWeightedGrade={old_final}  new finalWeightedGrade={new_final}")
    print(f"\nNew studentFeedback:\n{grader_json.get('studentFeedback','')}")

    if dry_run:
        print("\n[DRY RUN] No changes written.")
        return

    # ── Update blob ────────────────────────────────────────────────────────
    blob_data["grader_verdict"] = grader_json
    blob_data["final_grade"]   = new_final  # compute_final_grade already returns the full dict
    # Reset email flag so the cron job (or a manual send) will re-send
    blob_data["grade_email_sent"] = None

    _gcs_upload(blob_data, gs_uri)
    print(f"\nBlob updated. grade_email_sent reset to null — run send_grades.py to dispatch.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username",   required=True)
    parser.add_argument("--assignment", required=True)
    parser.add_argument("--dry-run",    action="store_true")
    args = parser.parse_args()
    run(args.username, args.assignment, args.dry_run)
