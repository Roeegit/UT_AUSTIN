# Admin TODO List
_Last updated: 2026-05-11_

---

## Waiting on external inputs

- [ ] **Post-exam survey link** — Create the Google Forms post-survey and paste the
  public URL into `backend/grade_email_template.py` → replace `POST_SURVEY_URL`.

- [ ] **Required students list** — Professor will send the list of student IDs that
  must take the AI exam for assignment 1. Upload to GCS:
  ```
  gs://ai-exam-submission/private/required_students_biu-os-2026-assignment-1-claude-code-shell-hooks.json
  ```
  Format: `["318277381", "123456789", ...]`  (9-digit full IDs)
  The `/api/admin/stats/{assignment}` endpoint will load this automatically.

- [ ] **Student email mapping** — Secretary to provide full_id → email mapping.
  Add an `email` column to `private/id_mapping.csv` on GCS (format: `full_id,hebrew_name,email`).
  Then implement `_load_email_map()` in `backend/scripts/send_grades.py`
  (stub + example code already in that function).

---

## Once email mapping is available

- [ ] **Send grade emails** — run manually first with dry-run to validate:
  ```bash
  python scripts/send_grades.py --unsent --dry-run
  python scripts/send_grades.py --unsent
  ```
  The script now skips students with missing fields (studentFeedback,
  studentStaticFeedback, hebrew_name, grade data) and prints which fields are missing.

- [ ] **9AM daily email job** — set up Cloud Scheduler to send unsent grades automatically:
  ```bash
  # Create the Cloud Run job (one-time)
  gcloud run jobs create send-grades-daily \
    --image me-west1-docker.pkg.dev/ai-examiner-system/ai-examiner-system-repo/backend:latest \
    --region me-west1 \
    --set-cloudsql-instances=ai-examiner-system:me-west1:ai-exam-db \
    --set-secrets=CLOUD_SQL_INSTANCE=CLOUD_SQL_INSTANCE:latest,DB_USER=DB_USER:latest,DB_PASS=DB_PASS:latest,DB_NAME=DB_NAME:latest,GCS_SUBMISSIONS_BUCKET=GCS_SUBMISSIONS_BUCKET:latest,SMTP_USER=SMTP_USER:latest,SMTP_PASSWORD=smtp-password:latest \
    --command=python --args="scripts/send_grades.py,--unsent"

  # Schedule it for 09:00 Israel time (UTC+3 = 06:00 UTC)
  gcloud scheduler jobs create http send-grades-9am \
    --schedule="0 6 * * *" \
    --uri="https://me-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/ai-examiner-system/jobs/send-grades-daily:run" \
    --message-body="{}" \
    --oauth-service-account-email=<YOUR_SERVICE_ACCOUNT_EMAIL> \
    --location=me-west1
  ```

---

## Google Forms — Pre-survey responses

- [ ] Share the Google Sheet linked to the pre-survey with the GCP service account email
  (Viewer access). Steps:
  1. Open the Form → Responses tab → click the green Sheets icon
  2. In the linked Sheet: Share → add service account email → Viewer
  After sharing, `GET /api/admin/stats/{assignment}` will show survey response counts.

- [ ] Run `python scripts/probe_google_apis.py --sheets` to discover the exact column
  headers and confirm the `id_col_hint` value for `extract_respondent_ids()`.

---

## Google Calendar — Slot registration

- [ ] Share the exam-slot calendar with the GCP service account email
  ("See all event details"). Already confirmed working (73 events found).
  The `/api/admin/stats/{assignment}` endpoint uses this automatically.

---

## Already done ✓

- [x] `grade_email_sent` column added to DB (migrated 2026-05-11)
- [x] `studentFeedback` (oral) shown in grade email and admin endpoint
- [x] `studentStaticFeedback` (code review) added to prompt + email + admin endpoint
- [x] `backfill_static_feedback.py` — re-runs code reviewer for existing graded sessions
- [x] `backfill_roster_fallback.py` — fixes matanmarx24 and similar missing-id sessions
- [x] Classroom roster CSV uploaded to GCS
- [x] Email validation: `validate_email_readiness()` — `send_grades.py` skips invalid sessions
- [x] `GET /api/admin/results/by-github/{username}` — returns `email_preview` + `email_validation`
- [x] `GET /api/admin/results/email-status?assignment=...` — lists all students with email sent/pending/invalid status
- [x] `GET /api/admin/stats/{assignment}` — per-assignment stats with Calendar, Sheets, required students, email status
