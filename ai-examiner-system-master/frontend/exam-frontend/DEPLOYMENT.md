# Deployment Guide — Oral Exam Frontend

## 1. Local Development Setup

### Prerequisites
- Node.js 18+
- Access to the backend Cloud Run service (or a local `gcloud` proxy)

### Install dependencies
```sh
cd frontend/exam-frontend
npm install
```

### Environment setup
Copy the example env file and fill in your values:
```sh
cp .env.local.example .env.local
```

Edit `.env.local`:
```env
# Point at the live backend (production)
BACKEND_URL=https://ai-exam-backend-dx6rlviobq-zf.a.run.app

# OR point at a local gcloud proxy (see below)
# BACKEND_URL=http://localhost:8080

# For local dev with a remote Cloud Run backend, provide a service account key:
GOOGLE_SA_KEY_JSON={"type":"service_account",...}

# Exam duration
EXAM_DURATION_SECONDS=900
NEXT_PUBLIC_EXAM_DURATION_SECONDS=900

# Enable QA mode (enables /qa, /qa/results, and /api/exam/results)
QA_MODE=true
NEXT_PUBLIC_QA_MODE=true
```

### Run the dev server
```powershell
cd frontend/exam-frontend; npm run dev
```

### Proxy backend locally (avoids service account key)
```powershell
gcloud run services proxy ai-exam-backend --port=8080 --region=me-west1
```
Then set `BACKEND_URL=http://localhost:8080` in `.env.local`.

### Proxy QA frontend service locally (IAM-protected services only)
```powershell
gcloud run services proxy exam-frontend-qa --port=3000 --region=me-west1
```

---

## 2. Backend Configuration for QA

Place the QA test data and assignment files in the backend directory:

### Assignment files
```
backend/assignments/qa_assignment_readme.md
backend/assignments/qa_assignment_readme_question_pool.json
```

### Student solution files
The backend reads student code from a configurable directory (e.g. `student_submissions/`).
Place the QA students there:
```
student_submissions/student-a/taskexec.c
student_submissions/student-a/utils.c
student_submissions/student-a/utils.h

student_submissions/student-b/taskexec.c
student_submissions/student-b/utils.c
student_submissions/student-b/utils.h

student_submissions/student-c/taskexec.c
student_submissions/student-c/utils.c
student_submissions/student-c/utils.h
```

The QA page will start exams with:
- `assignment_name=qa_assignment`
- `student_id=student-a` / `student-b` / `student-c`
- `github_username=student-a` / `student-b` / `student-c`

---

## 3. Cloud Run Deployment

### Authenticate
```powershell
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Validate current account/project
```powershell
gcloud config list
```

### Build and deploy — QA mode (public, for QA testers)
```powershell
gcloud builds submit --config cloudbuild-frontend.yaml .
```

### Build and deploy — Production mode (IAM-protected, accessed via Chrome kiosk)
```powershell
gcloud builds submit --config cloudbuild-frontend-prod.yaml .
```

> **Note:** `NEXT_PUBLIC_QA_MODE` is a Docker **build ARG** baked into the JS bundle at build time.
> Do NOT use `gcloud run deploy --source --set-env-vars` — that only sets runtime vars and the
> ARG will silently default to `false`, breaking the `/qa` page. Always use `gcloud builds submit`
> with the yaml files above.

### Using Secret Manager for the SA key
```powershell
gcloud secrets create google-sa-key --data-file=-
gcloud run services update exam-frontend --region me-west1 --set-secrets "GOOGLE_SA_KEY_JSON=google-sa-key:latest"
```

---

## 4. Switching Between QA and Production

| Service | Access | Purpose |
|---|---|---|
| `exam-frontend-qa` | Public (`--allow-unauthenticated`) | QA testers |
| `exam-frontend` | IAM-protected (`--no-allow-unauthenticated`) | Production via Chrome kiosk |

---

## 5. QA Workflow Summary

1. Deploy `exam-frontend-qa` with `QA_MODE=true`.
2. Navigate to `https://<qa-url>/qa`.
3. Select a student profile (student-a / student-b / student-c) and a persona.
4. Click "התחל בחינה" — the exam starts automatically.
5. After the exam completes, click "צפה בתוצאות ←" to view the graded results.
6. The results page polls `/api/exam/results?student_id=X` every 5 seconds until grading completes.
