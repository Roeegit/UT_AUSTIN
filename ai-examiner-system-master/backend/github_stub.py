"""
github_stub.py — GitHub App–authenticated submission fetcher.

Auth flow (GitHub App):
  1. Sign a short-lived JWT with the app's RSA private key  (PyJWT + RS256)
  2. Exchange JWT for an Installation Access Token          (POST /app/installations/{id}/access_tokens)
  3. Use the token for all subsequent API calls

Repo resolution (pattern-based — no Classroom API):
  Derives the student's repo full name from two env vars:
    GITHUB_ORG          — the GitHub organisation that owns all student repos
    GITHUB_REPO_PATTERN — Python format string, receives `github_username`
                          (and optionally `assignment_name` from config)
  Examples:
    GITHUB_ORG=BIU-OS-2025
    GITHUB_REPO_PATTERN=ex2-{github_username}
    → full name: "BIU-OS-2025/ex2-johndoe"

File download:
  GET /repos/{owner}/{repo}/contents/{path}
  Decodes base64 content and saves each file to GCS:
    gs://{GCS_SUBMISSIONS_BUCKET}/{assignment_name}/{github_username}/{filename}

Required environment variables:
  GITHUB_APP_ID           — numeric App ID (from App settings page)
  GITHUB_PRIVATE_KEY      — full PEM text of the app's private key
                             (newlines may be literal or escaped as \\n)
  GITHUB_PRIVATE_KEY_PATH — alternative: path to the .pem file
                             (used if GITHUB_PRIVATE_KEY is not set)
  GITHUB_INSTALLATION_ID  — installation ID (from the org/account that installed the app)
  GITHUB_ORG              — GitHub organisation that owns the student repos
  GITHUB_REPO_PATTERN     — pattern string, e.g. "ex2-{github_username}"
  GITHUB_BRANCH           — branch to read files from (default: "main")
  GITHUB_FILES_PATH       — subfolder inside the repo ("" = root)
  GCS_SUBMISSIONS_BUCKET  — GCS bucket name for storing student submissions
"""

import base64
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import jwt  # PyJWT — pip install "PyJWT[cryptography]"
import requests as http_requests
from google.cloud import storage as gcs

from config import (
    ASSIGNMENT_FILES,
    ASSIGNMENT_REPO_PATTERNS,
    GITHUB_BRANCH,
    GITHUB_FILES_PATH,
    GITHUB_ORG,
    GITHUB_REPO_PATTERN,
    STUDENT_FILES,
)

# ---------------------------------------------------------------------------
# GCS client (module-level, reused across requests)
# ---------------------------------------------------------------------------

# _gcs_client = gcs.Client()

try:
    _gcs_client = gcs.Client()
except Exception:
    _gcs_client = None

def _bucket():
    bucket_name = os.environ["GCS_SUBMISSIONS_BUCKET"].strip()
    return _gcs_client.bucket(bucket_name)


def _gcs_path(assignment_name: str, github_username: str, filename: str) -> str:
    """GCS object path: {assignment_name}/{github_username}/{filename}"""
    return f"{assignment_name}/{github_username}/{filename}"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    github_username: str
    repo:            str
    files_saved:     list[str] = field(default_factory=list)
    files_missing:   list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.files_saved) > 0


# ---------------------------------------------------------------------------
# GitHub App authentication
# ---------------------------------------------------------------------------

def _load_private_key() -> str:
    """
    Load the RSA private key PEM.
    Checks GITHUB_PRIVATE_KEY (env string) then GITHUB_PRIVATE_KEY_PATH (file).
    Handles both literal newlines and escaped \\n sequences.
    """
    pem = os.environ.get("GITHUB_PRIVATE_KEY", "")
    if pem:
        return pem.replace("\\n", "\n")

    path = os.environ.get("GITHUB_PRIVATE_KEY_PATH", "")
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    raise ValueError(
        "GitHub App private key not found. "
        "Set GITHUB_PRIVATE_KEY (PEM text) or GITHUB_PRIVATE_KEY_PATH (path to .pem file)."
    )


def _generate_app_jwt() -> str:
    app_id = os.environ.get("GITHUB_APP_ID", "")
    if not app_id:
        raise ValueError("GITHUB_APP_ID environment variable is not set.")

    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (5 * 60),
        "iss": app_id,
    }
    return jwt.encode(payload, _load_private_key(), algorithm="RS256")


def _get_installation_token() -> str:
    installation_id = os.environ.get("GITHUB_INSTALLATION_ID", "")
    if not installation_id:
        raise ValueError("GITHUB_INSTALLATION_ID environment variable is not set.")

    app_jwt = _generate_app_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

    resp = http_requests.post(
        url,
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=15,
    )

    if not resp.ok:
        raise RuntimeError(
            f"Failed to obtain GitHub App installation token: "
            f"HTTP {resp.status_code} — {resp.text[:300]}"
        )

    return resp.json()["token"]


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


# ---------------------------------------------------------------------------
# Repo resolution: pattern-based (no Classroom API)
# ---------------------------------------------------------------------------

def _find_most_recent_variant(base_name: str, token: str) -> str:
    """
    GitHub Classroom sometimes creates suffixed repos (e.g. -2, -3) when a student
    re-accepts an assignment whose original repo already exists.  Check the base name
    and suffixed variants up to -5; return whichever was pushed most recently so the
    student's actual work is always used instead of the original skeleton.
    """
    candidates = [base_name] + [f"{base_name}-{i}" for i in range(1, 6)]
    headers = _auth_headers(token)

    def _probe(name: str) -> tuple[str, str]:
        url = f"https://api.github.com/repos/{GITHUB_ORG}/{name}"
        try:
            resp = http_requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                return name, resp.json().get("pushed_at", "")
        except Exception:
            pass
        return name, ""

    best_name = base_name
    best_pushed_at = ""

    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        for name, pushed_at in pool.map(_probe, candidates):
            if pushed_at > best_pushed_at:
                best_pushed_at = pushed_at
                best_name = name

    if best_name != base_name:
        print(f"[GitHub] Suffixed variant detected — using '{best_name}' (most recently pushed)")
    return best_name


def _resolve_repo_full_name(github_username: str, assignment_name: str, token: str | None = None) -> str:
    if not GITHUB_ORG:
        raise ValueError("GITHUB_ORG environment variable is not set.")

    # Use per-assignment pattern if defined, else fall back to global env var.
    pattern = ASSIGNMENT_REPO_PATTERNS.get(assignment_name, GITHUB_REPO_PATTERN)
    if not pattern:
        raise ValueError("GITHUB_REPO_PATTERN environment variable is not set.")

    try:
        base_name = pattern.format(
            github_username=github_username,
            assignment_name=assignment_name,
        )
    except KeyError as exc:
        raise ValueError(
            f"GITHUB_REPO_PATTERN contains an unknown placeholder: {exc}. "
            f"Supported: {{github_username}}, {{assignment_name}}"
        ) from exc

    repo_name = _find_most_recent_variant(base_name, token) if token else base_name
    full_name = f"{GITHUB_ORG}/{repo_name}"
    print(f"[GitHub] Resolved repo → {full_name}")
    return full_name


# ---------------------------------------------------------------------------
# File download via Contents API
# ---------------------------------------------------------------------------

def _fetch_one_file(repo_full_name: str, filename: str, token: str) -> str | None:
    subfolder = GITHUB_FILES_PATH.strip("/")
    in_repo_path = f"{subfolder}/{filename}" if subfolder else filename

    url = f"https://api.github.com/repos/{repo_full_name}/contents/{in_repo_path}"
    params = {"ref": GITHUB_BRANCH}

    try:
        resp = http_requests.get(
            url, headers=_auth_headers(token), params=params, timeout=15
        )
    except http_requests.RequestException as exc:
        print(f"[GitHub] Network error fetching {filename}: {exc}")
        return None

    if resp.status_code == 404:
        print(f"[GitHub] 404 — {filename} not found in {repo_full_name}")
        return None

    if not resp.ok:
        print(f"[GitHub] HTTP {resp.status_code} for {filename}: {resp.text[:120]}")
        return None

    data = resp.json()
    if data.get("encoding") != "base64":
        print(f"[GitHub] Unexpected encoding for {filename}: {data.get('encoding')}")
        return None

    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace").strip()
    except Exception as exc:
        print(f"[GitHub] Decode error for {filename}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Public: fetch from GitHub and save to GCS
# ---------------------------------------------------------------------------

def fetch_and_save_submission(
    github_username: str, assignment_name: str
) -> FetchResult:
    """
    Full pipeline:
      1. Generate a GitHub App JWT and exchange it for an installation token.
      2. Derive the student's repo name from GITHUB_ORG + GITHUB_REPO_PATTERN.
      3. Download each file in ASSIGNMENT_FILES via the Contents API.
      4. Save files to GCS at  {assignment_name}/{github_username}/{filename}.

    Returns a FetchResult describing what was saved vs. what was missing.
    """
    print(f"[GitHub App] Authenticating as App installation...")
    token = _get_installation_token()

    repo_full_name = _resolve_repo_full_name(github_username, assignment_name, token)

    result = FetchResult(
        github_username = github_username,
        repo            = repo_full_name,
    )

    bucket = _bucket()
    print(f"[GitHub] Fetching files from {repo_full_name} → GCS {assignment_name}/{github_username}/")

    for filename in ASSIGNMENT_FILES.get(assignment_name, STUDENT_FILES):
        content = _fetch_one_file(repo_full_name, filename, token)

        if content is not None:
            blob = bucket.blob(_gcs_path(assignment_name, github_username, filename))
            blob.upload_from_string(content, content_type="text/plain; charset=utf-8")
            result.files_saved.append(filename)
            print(f"[GitHub]   ✓ saved  {filename}  ({len(content):,} chars)")
        else:
            result.files_missing.append(filename)

    return result


# ---------------------------------------------------------------------------
# Public: fetch a single file from GitHub (used for id.txt at grading time)
# ---------------------------------------------------------------------------

def fetch_single_file(
    github_username: str, assignment_name: str, filename: str
) -> tuple[str | None, str | None]:
    """
    Fetch one file from the student's repo without saving to GCS.
    Returns (content, error_message). One of them is always None.
    """
    try:
        token = _get_installation_token()
    except Exception as exc:
        return None, str(exc)

    try:
        repo_full_name = _resolve_repo_full_name(github_username, assignment_name, token)
    except ValueError as exc:
        return None, str(exc)

    subfolder = GITHUB_FILES_PATH.strip("/")
    in_repo_path = f"{subfolder}/{filename}" if subfolder else filename
    url = f"https://api.github.com/repos/{repo_full_name}/contents/{in_repo_path}"

    try:
        resp = http_requests.get(
            url, headers=_auth_headers(token), params={"ref": GITHUB_BRANCH}, timeout=15
        )
    except http_requests.RequestException as exc:
        return None, f"network error: {exc}"

    if resp.status_code == 404:
        return None, "404"

    if not resp.ok:
        return None, f"HTTP {resp.status_code}"

    data = resp.json()
    if data.get("encoding") != "base64":
        return None, f"unexpected encoding: {data.get('encoding')}"

    try:
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace").strip()
        return content, None
    except Exception as exc:
        return None, f"decode error: {exc}"


# ---------------------------------------------------------------------------
# Public: load already-saved files from GCS (used by exam endpoints)
# ---------------------------------------------------------------------------

def load_local_submission(github_username: str, assignment_name: str) -> dict[str, str]:
    """
    Read the previously fetched files from GCS at {assignment_name}/{github_username}/.
    Returns {filename: content} for every file in ASSIGNMENT_FILES.
    Missing files get an empty string — build_exam_context marks them as [NOT SUBMITTED].
    """
    bucket = _bucket()
    files: dict[str, str] = {}

    for filename in ASSIGNMENT_FILES.get(assignment_name, STUDENT_FILES):
        blob = bucket.blob(_gcs_path(assignment_name, github_username, filename))
        try:
            files[filename] = blob.download_as_text(encoding="utf-8").strip()
        except Exception:
            files[filename] = ""

    return files


# ---------------------------------------------------------------------------
# Build examiner context string from loaded files
# ---------------------------------------------------------------------------

# Administrative files the examiner must never see or question. They are kept in
# ASSIGNMENT_FILES (so they are still fetched/loaded for ID resolution and the
# extended-time accommodation check), but they carry no code to defend — id.txt is
# just the student's ID digits — so showing them only invites pointless "why is
# id.txt missing?" questions (and leaks the ID into the prompt). Filtered out here.
EXAMINER_HIDDEN_FILES = {"id.txt"}


def build_exam_context(assignment_readme: str, student_files: dict[str, str]) -> str:
    """
    Build the full context string passed to the examiner on turn 1.
    An empty content string means the file was not submitted.
    Administrative files (EXAMINER_HIDDEN_FILES) are skipped entirely — the examiner
    neither sees them nor is prompted to ask why a missing one is absent.
    """
    context = "[ASSIGNMENT INSTRUCTIONS]\n"
    context += f"--- File: README ---\n{assignment_readme}\n\n"
    context += "[STUDENT SUBMITTED FILES]\n"

    for filename, content in student_files.items():
        if filename in EXAMINER_HIDDEN_FILES:
            continue
        if content:
            context += f"\n--- File: {filename} ---\n{content}\n"
        else:
            context += (
                f"\n--- File: {filename} --- [NOT SUBMITTED]\n"
                f"This file was not found in the student's submission. "
                f"Ask exactly ONE light question about it: what was it supposed to do "
                f"and why is it missing? Do not ask technical line-level questions about "
                f"code you cannot see. Log the student's explanation — it is a valuable "
                f"integrity signal. Then move on; do not dwell on it.\n"
            )

    return context
