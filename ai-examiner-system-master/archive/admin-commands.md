# Admin Commands — Cloud Shell (bash)

Backend URL: `https://ai-exam-backend-dx6rlviobq-zf.a.run.app`

---

## Invalidate a student session (allow retake)

Replace `<github_username>` with the student's GitHub username.
Uses the assignment set in the backend's `ASSIGNMENT_NAME` env var (default: `test-assignment`).
Also clears `complaint_pending` status — use this to unblock a student after reviewing their complaint.

```bash
TOKEN=$(gcloud auth print-identity-token --audiences=https://ai-exam-backend-dx6rlviobq-zf.a.run.app)
curl -s -X POST "https://ai-exam-backend-dx6rlviobq-zf.a.run.app/api/admin/invalidate/<github_username>" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### Quick one-liner for shacharsl97 / test-assignment

```bash
TOKEN=$(gcloud auth print-identity-token --audiences=https://ai-exam-backend-dx6rlviobq-zf.a.run.app) && curl -s -X POST "https://ai-exam-backend-dx6rlviobq-zf.a.run.app/api/admin/invalidate/shacharsl97" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## View results for a student

```bash
TOKEN=$(gcloud auth print-identity-token --audiences=https://ai-exam-backend-dx6rlviobq-zf.a.run.app)
curl -s "https://ai-exam-backend-dx6rlviobq-zf.a.run.app/api/admin/results/<github_username>" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## Invalidate a student session — **ex1** deployment

Replace `<github_username>` with the student's GitHub username.
This targets the `ai-exam-backend-ex1` service (assignment: `biu-os-2026-assignment-1-claude-code-shell-hooks`).

```bash
TOKEN=$(gcloud auth print-identity-token --audiences=https://ai-exam-backend-ex1-dx6rlviobq-zf.a.run.app)
curl -s -X POST "https://ai-exam-backend-ex1-dx6rlviobq-zf.a.run.app/api/admin/invalidate/Idozarky" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## Re-grade a session (re-run code reviewer + grader)

Get `<session_id>` from SQL: `SELECT session_id FROM sessions WHERE github_username = '<username>' ORDER BY start_time DESC LIMIT 1;`

Replace `<VIEWER_PASSWORD>` with the value of the `VIEWER_PASSWORD` secret.

```bash
# For test-assignment (via exam-admin frontend):
curl -X POST "https://exam-admin-dx6rlviobq-zf.a.run.app/api/admin/regrade/<session_id>" \
  -H "X-Admin-Key: <VIEWER_PASSWORD>"

# For ex1 (via exam-admin-ex1 frontend, if configured, or directly):
curl -X POST "https://exam-admin-ex1-dx6rlviobq-zf.a.run.app/api/admin/regrade/<session_id>" \
  -H "X-Admin-Key: <VIEWER_PASSWORD>"
```

Returns immediately with `{"status":"regrade_started"}`. Check Cloud Logging for `[Grader] Model=... keys=[...]` to confirm what fields Claude returned.

---

## Notes
- Run these in **Google Cloud Shell** (browser-based, already authenticated).
- The `gcloud auth print-identity-token` command mints a short-lived token — re-run if you get 401.
- Make sure you are logged in as `sarne.lab@gmail.com` in Cloud Shell.
