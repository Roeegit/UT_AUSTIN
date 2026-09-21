# Automated Oral Exam System — Frontend Architecture & Implementation Prompt

---

## Part 1: Architecture Analysis & Recommendations

### 1. Frontend Framework: Next.js on Cloud Run.

**Recommendation: Next.js (App Router) deployed as a second Cloud Run service.**

Rationale:

- **Server-side API routes solve the auth problem.** The kiosk browser never touches Google identity tokens. Next.js API routes run server-side, hold a GCP service account key, mint identity tokens, and proxy requests to the backend Cloud Run service. The browser only talks to the Next.js service.
- **No SSR needed for page rendering** — the exam UI is a single interactive page, so it's effectively an SPA. But Next.js API routes give us a "backend-for-frontend" (BFF) layer without deploying a separate proxy server.
- **Cloud Run hosting is consistent** with the existing backend. Same project, same region (`me-west1`), same IAM patterns. The Next.js service runs as a Docker container.
- **Kiosk context means no SEO, no progressive enhancement concerns.** We control the browser. A React SPA behind Next.js API routes is ideal.

Alternatives considered:
- *Pure SPA (Vite + React) + separate Express proxy*: works, but two things to deploy and maintain.
- *Relaxing Cloud Run auth + API key on admin endpoints*: exposes the backend publicly. Any student could hit unauthenticated endpoints with curl. Not recommended.
- *Cloud Run IAM invoker on the frontend service account*: this is the right pattern. The Next.js Cloud Run service's service account gets `roles/run.invoker` on the backend service. Zero public exposure.

### 2. Authentication & Security Design

```
┌──────────────────────┐       ┌─────────────────────────┐       ┌──────────────────────┐
│   Kiosk Browser      │       │  Next.js on Cloud Run   │       │  Backend (FastAPI)    │
│   (student facing)   │──────▶│  (BFF / proxy layer)    │──────▶│  on Cloud Run         │
│                      │ HTTP  │                          │ HTTP  │  --no-allow-unauth    │
│  No credentials.     │       │  Holds SA key.           │  +ID  │                      │
│  Talks only to BFF.  │       │  Mints ID tokens.        │ token │                      │
│                      │       │  Blocks admin routes.    │       │                      │
└──────────────────────┘       └─────────────────────────┘       └──────────────────────┘
```

**How it works:**

1. The Next.js Cloud Run service runs with a dedicated service account (e.g., `exam-frontend@ai-examiner-system.iam.gserviceaccount.com`).
2. That service account is granted `roles/run.invoker` on the backend Cloud Run service.
3. Next.js API routes use `google-auth-library` to generate an ID token targeting the backend's URL, then forward the request with `Authorization: Bearer <id_token>`.
4. **Admin endpoint protection**: The Next.js BFF simply does *not expose* proxy routes for admin endpoints. There is no `/api/proxy/admin/*` route. The TA uses a separate tool (curl, Postman, or a small admin CLI) with their own credentials.
5. **Session scoping**: The backend already uses UUID session IDs. The BFF passes `student_id` at start and receives a `session_id`. All subsequent calls are scoped to that session. No cross-student access is possible since the student never sees other session IDs.
6. **Kiosk initialization**: The TA navigates to `https://<frontend-url>/exam?student_id=<ID>` before the student sits down, or a small launcher script does this. The `student_id` is in the URL — acceptable because (a) the room is proctored, (b) the kiosk is locked down, (c) knowing another student's ID doesn't help since `start` is idempotent per student.

**Why the frontend is `--allow-unauthenticated` and why that's safe:**

The kiosk browser (operated by the student) is the intended client of the frontend. It cannot hold Google credentials, so the frontend must be reachable without IAM auth. This is safe because:

- The frontend only exposes three student-scoped routes (`start`, `answer`, `timeout`). Admin endpoints are **not proxied at all** — no route exists.
- Even if a student bypassed the kiosk lockdown and used curl, they could only call the same three endpoints the UI calls — no escalation path.
- Sessions are scoped by UUID; a student cannot interfere with another student's session.

**Network restriction (recommended):** To prevent access from outside the exam room (e.g., a student's phone), apply a Google Cloud Armor security policy that allowlists only the university's IP range:

```bash
# Create a Cloud Armor policy allowing only university IPs
gcloud compute security-policies create exam-frontend-policy \
  --project=ai-examiner-system

gcloud compute security-policies rules create 1000 \
  --security-policy=exam-frontend-policy \
  --src-ip-ranges="<UNIVERSITY_IP_RANGE>" \
  --action=allow

gcloud compute security-policies rules update 2147483647 \
  --security-policy=exam-frontend-policy \
  --action=deny-403

# Attach to the frontend service via a Load Balancer
# (Cloud Armor requires a Global External ALB in front of Cloud Run)
```

Alternatively, if Cloud Armor + ALB is too heavy, configure the exam room's network so that kiosk PCs route to the frontend URL and block it from the guest Wi-Fi.

### 3. UI Component Architecture

```
<ExamPage>                          ← top-level page, manages all state
  ├── <ExamLayout>                  ← CSS grid: two-panel split
  │     ├── <CodePanel>             ← left panel
  │     │     ├── <AssignmentHeader>← assignment name label
  │     │     ├── <FileTabBar>      ← tabs for each source file
  │     │     └── <CodeViewer>      ← Monaco Editor (read-only mode)
  │     │           └── highlight/scroll logic for JUMP_TO_LINE
  │     └── <ExamPanel>             ← right panel
  │           ├── <Timer>           ← countdown, triggers timeout API call
  │           ├── <QuestionDisplay> ← current question text (not chat history)
  │           ├── <AnswerInput>     ← textarea + submit button
  │           └── <CompletedScreen> ← shown when exam ends
  └── (no header/nav — kiosk mode, full viewport)
```

**State management**: All state lives in `ExamPage` via `useState`/`useReducer`. No need for a global store — it's a single page with a linear flow.

Key state:
- `phase`: `"loading" | "active" | "completed" | "error"`
- `sessionId`: from `/api/auth/start` response
- `assignmentName`: display label for the assignment (e.g., "Assignment 3: Virtual Memory")
- `files`: `Map<filename, content>` — source files for the code viewer
- `currentFile`: which file tab is active
- `question`: current question text
- `action`: `{ type, file, line }` — drives JUMP_TO_LINE
- `timeRemaining`: seconds left
- `isSubmitting`: loading state for answer submission

### 4. Source Files Strategy

The backend's `POST /api/auth/start` should return (or we add to its response) the student's source files. If it doesn't currently, there are two options:

- **Option A (preferred)**: Add a field to the `/api/auth/start` response: `"files": { "main.c": "...", "utils.h": "..." }`. The backend already has these files in GCS and loads them for the AI examiner. Returning them to the frontend is trivial.
- **Option B**: Add a new endpoint `GET /api/exam/files/{session_id}` that returns the files. The BFF calls this right after `start`.

Either way, the BFF fetches the files server-side and sends them to the browser as JSON. The browser caches them in React state for the duration of the exam. Files are typically small (a few KB of C/Python code).

### 5. JUMP_TO_LINE Flow

1. Student submits answer → BFF proxies to `POST /api/exam/answer`.
2. Response includes `{ question_text, action: "JUMP_TO_LINE", action_file: "main.c", action_line: 42 }`.
3. `ExamPage` updates state: `setCurrentFile("main.c")`, `setAction({ type: "JUMP_TO_LINE", file: "main.c", line: 42 })`.
4. `FileTabBar` switches to the `main.c` tab.
5. `CodeViewer` (Monaco Editor) receives the line number via prop/effect, calls `editor.revealLineInCenter(42)` and adds a line decoration (yellow highlight background) on line 42.
6. Previous highlight is cleared before applying the new one.

---

## Part 2: Implementation Prompt for Claude Code

Everything below this line is the self-contained prompt to give to Claude Code.

---

# Claude Code Prompt: Build the Oral Exam Frontend

## Context

You are building the frontend for an Automated Oral Exam system used in a university OS course. The backend (FastAPI on Google Cloud Run) already exists. You are building a **Next.js application** that serves as both the exam UI and a backend-for-frontend (BFF) proxy to the FastAPI backend.

The exam works like this: students sit at locked-down kiosk PCs in a proctored room. The screen shows a split view — code on the left, exam questions on the right. An AI examiner asks 3 questions about the student's submitted code. Students type answers. The AI responds with follow-up questions and can point to specific lines in the code.

## Tech Stack

- **Next.js 14+** (App Router) with TypeScript
- **React 18+**
- **Monaco Editor** (`@monaco-editor/react`) for the code viewer panel
- **Tailwind CSS** for styling
- **google-auth-library** for minting GCP identity tokens server-side
- **Deployed as a Docker container on Google Cloud Run** (same project: `ai-examiner-system`, region: `me-west1`)

## Project Structure

Create this exact file/folder structure:

```
exam-frontend/
├── Dockerfile
├── .dockerignore
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
├── .env.local.example          # template for env vars
├── src/
│   ├── app/
│   │   ├── layout.tsx          # root layout (minimal — no nav, kiosk mode)
│   │   ├── globals.css         # Tailwind imports + kiosk overrides
│   │   ├── exam/
│   │   │   └── page.tsx        # the exam page (reads ?student_id= from URL)
│   │   └── api/
│   │       └── exam/
│   │           ├── start/
│   │           │   └── route.ts    # POST — proxies to backend /api/auth/start
│   │           ├── answer/
│   │           │   └── route.ts    # POST — proxies to backend /api/exam/answer
│   │           └── timeout/
│   │               └── route.ts    # POST — proxies to backend /api/exam/timeout
│   ├── components/
│   │   ├── ExamLayout.tsx      # two-panel CSS grid container
│   │   ├── CodePanel.tsx       # left panel: file tabs + Monaco viewer
│   │   ├── FileTabBar.tsx      # horizontal tab bar for source files
│   │   ├── CodeViewer.tsx      # Monaco Editor wrapper (read-only)
│   │   ├── ExamPanel.tsx       # right panel: question + answer + timer
│   │   ├── Timer.tsx           # countdown timer component
│   │   ├── QuestionDisplay.tsx # displays current question text
│   │   ├── AnswerInput.tsx     # textarea + submit button
│   │   └── CompletedScreen.tsx # shown when exam finishes
│   ├── lib/
│   │   ├── backend-proxy.ts    # server-side helper: mint ID token + fetch backend
│   │   └── types.ts            # TypeScript interfaces for API responses
│   └── hooks/
│       └── useExamState.ts     # custom hook: manages exam state machine
```

## Environment Variables

Create `.env.local.example` with these variables:

```env
# URL of the FastAPI backend Cloud Run service (no trailing slash)
BACKEND_URL=https://ai-examiner-backend-XXXXX-me-west1.a.run.app

# Google Cloud service account credentials JSON (for minting ID tokens).
# In production on Cloud Run, leave this empty — the default SA is used.
# For local dev, paste the JSON key contents here or set GOOGLE_APPLICATION_CREDENTIALS path.
GOOGLE_SA_KEY_JSON=

# Exam duration in seconds (default: 900 = 15 minutes)
EXAM_DURATION_SECONDS=900
```

## Detailed Implementation

### 1. `src/lib/types.ts`

```typescript
export interface ExamStartRequest {
  student_id: string;
}

export interface ExamStartResponse {
  session_id: string;
  student_id: string;
  assignment_name: string;  // e.g. "Assignment 3: Virtual Memory"
  question_text: string;
  action: "JUMP_TO_LINE" | "NONE" | string;
  action_file?: string;
  action_line?: number;
  files: Record<string, string>;  // filename -> content
  // If the backend doesn't return files here, we'll need a separate call.
  // See "Source Files" section below.
}

export interface ExamAnswerRequest {
  session_id: string;
  answer_text: string;
}

export interface ExamAnswerResponse {
  question_text: string;
  action: "JUMP_TO_LINE" | "NONE" | string;
  action_file?: string;
  action_line?: number;
  is_complete: boolean;  // true when all 3 questions are done
}

export interface ExamTimeoutRequest {
  session_id: string;
}

export interface ExamAction {
  type: string;
  file?: string;
  line?: number;
}

export type ExamPhase = "loading" | "active" | "completed" | "error";
```

**IMPORTANT about `files`**: The backend's `/api/auth/start` may not currently return the source files. Check the backend code. If it does not, you need to either:
- (a) Ask me to add a `files` field to the backend response, OR
- (b) Create an additional proxy route `GET /api/exam/files?session_id=X` that calls a backend endpoint to fetch the files.

For now, **assume Option A** — the start response includes `files`. If it doesn't, use placeholder file content during development and leave a `// TODO` comment.

### 2. `src/lib/backend-proxy.ts`

This is the critical server-side module. It mints a Google identity token and proxies requests to the FastAPI backend.

```typescript
import { GoogleAuth } from "google-auth-library";

let auth: GoogleAuth;

function getAuth(): GoogleAuth {
  if (auth) return auth;

  const saKeyJson = process.env.GOOGLE_SA_KEY_JSON;

  if (saKeyJson) {
    // Local dev: use explicit service account key
    const credentials = JSON.parse(saKeyJson);
    auth = new GoogleAuth({
      credentials,
      scopes: [], // not needed for ID tokens
    });
  } else {
    // Cloud Run: use default service account (automatic)
    auth = new GoogleAuth();
  }

  return auth;
}

export async function proxyToBackend(
  path: string, // e.g. "/api/auth/start"
  options: {
    method: "GET" | "POST";
    body?: unknown;
  }
): Promise<Response> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) throw new Error("BACKEND_URL not configured");

  const targetUrl = `${backendUrl}${path}`;

  // Get an ID token for the backend Cloud Run service
  const client = await getAuth().getIdTokenClient(backendUrl);
  const headers = await client.getRequestHeaders();

  const response = await fetch(targetUrl, {
    method: options.method,
    headers: {
      ...headers,
      "Content-Type": "application/json",
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  return response;
}
```

**Key point**: `getIdTokenClient(backendUrl)` generates an ID token with the audience set to the backend URL, which is exactly what Cloud Run IAM authentication requires. On Cloud Run, the default service account is used automatically. Locally, the SA key JSON is used.

### 3. API Route Handlers

Each route handler is thin — validate input, call `proxyToBackend`, return the response.

#### `src/app/api/exam/start/route.ts`

```typescript
import { NextRequest, NextResponse } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { student_id } = body;

    if (!student_id || typeof student_id !== "string") {
      return NextResponse.json({ error: "student_id is required" }, { status: 400 });
    }

    const backendRes = await proxyToBackend("/api/auth/start", {
      method: "POST",
      body: { student_id },
    });

    const data = await backendRes.json();

    if (!backendRes.ok) {
      return NextResponse.json(data, { status: backendRes.status });
    }

    return NextResponse.json(data);
  } catch (err) {
    console.error("Start exam error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
```

#### `src/app/api/exam/answer/route.ts`

Same pattern: extract `{ session_id, answer_text }` from body, validate, proxy to `/api/exam/answer`.

#### `src/app/api/exam/timeout/route.ts`

Same pattern: extract `{ session_id }` from body, validate, proxy to `/api/exam/timeout`.

**CRITICAL: Do NOT create proxy routes for admin endpoints** (`/api/admin/*`). The BFF intentionally does not expose these. Admin access happens through a separate channel (direct curl/Postman with the TA's own Google credentials).

### 4. `src/hooks/useExamState.ts`

This custom hook encapsulates the entire exam state machine.

```typescript
import { useState, useCallback, useRef, useEffect } from "react";
import type {
  ExamPhase,
  ExamAction,
  ExamStartResponse,
  ExamAnswerResponse,
} from "@/lib/types";

interface ExamState {
  phase: ExamPhase;
  sessionId: string | null;
  assignmentName: string;
  files: Record<string, string>;
  currentFile: string | null;
  questionText: string;
  questionNumber: number;
  action: ExamAction | null;
  timeRemaining: number;
  isSubmitting: boolean;
  error: string | null;
}

export function useExamState(examDurationSeconds: number) {
  const [state, setState] = useState<ExamState>({
    phase: "loading",
    sessionId: null,
    assignmentName: "",
    files: {},
    currentFile: null,
    questionText: "",
    questionNumber: 1,
    action: null,
    timeRemaining: examDurationSeconds,
    isSubmitting: false,
    error: null,
  });

  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // --- Timer logic ---
  // Start a 1-second interval that decrements timeRemaining.
  // When it hits 0, call handleTimeout().
  // Store the interval ref so we can clear it on unmount or exam completion.

  const startTimer = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setState((prev) => {
        if (prev.timeRemaining <= 1) {
          // Time's up — will trigger timeout in an effect
          return { ...prev, timeRemaining: 0 };
        }
        return { ...prev, timeRemaining: prev.timeRemaining - 1 };
      });
    }, 1000);
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopTimer(); // cleanup on unmount
  }, [stopTimer]);

  // --- API calls ---

  const startExam = useCallback(async (studentId: string) => {
    try {
      const res = await fetch("/api/exam/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id: studentId }),
      });

      if (!res.ok) {
        const err = await res.json();
        setState((prev) => ({
          ...prev,
          phase: "error",
          error: err.error || `Start failed (${res.status})`,
        }));
        return;
      }

      const data: ExamStartResponse = await res.json();
      const fileNames = Object.keys(data.files || {});

      setState((prev) => ({
        ...prev,
        phase: "active",
        sessionId: data.session_id,
        assignmentName: data.assignment_name || "",
        files: data.files || {},
        currentFile: data.action_file || fileNames[0] || null,
        questionText: data.question_text,
        questionNumber: 1,
        action:
          data.action === "JUMP_TO_LINE"
            ? { type: data.action, file: data.action_file, line: data.action_line }
            : null,
      }));

      startTimer();
    } catch (err) {
      setState((prev) => ({
        ...prev,
        phase: "error",
        error: "Network error — could not reach exam server.",
      }));
    }
  }, [startTimer]);

  const submitAnswer = useCallback(async (answerText: string) => {
    if (!state.sessionId || state.isSubmitting) return;

    setState((prev) => ({ ...prev, isSubmitting: true }));

    try {
      const res = await fetch("/api/exam/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: state.sessionId,
          answer_text: answerText,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        setState((prev) => ({
          ...prev,
          isSubmitting: false,
          error: err.error || "Failed to submit answer",
        }));
        return;
      }

      const data: ExamAnswerResponse = await res.json();

      if (data.is_complete) {
        stopTimer();
        setState((prev) => ({
          ...prev,
          phase: "completed",
          isSubmitting: false,
          questionText: "",
        }));
        return;
      }

      setState((prev) => ({
        ...prev,
        isSubmitting: false,
        questionText: data.question_text,
        questionNumber: prev.questionNumber + 1,
        currentFile:
          data.action === "JUMP_TO_LINE" && data.action_file
            ? data.action_file
            : prev.currentFile,
        action:
          data.action === "JUMP_TO_LINE"
            ? { type: data.action, file: data.action_file, line: data.action_line }
            : null,
      }));
    } catch {
      setState((prev) => ({
        ...prev,
        isSubmitting: false,
        error: "Network error — could not submit answer.",
      }));
    }
  }, [state.sessionId, state.isSubmitting, stopTimer]);

  const handleTimeout = useCallback(async () => {
    if (!state.sessionId) return;
    stopTimer();

    try {
      await fetch("/api/exam/timeout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: state.sessionId }),
      });
    } catch {
      // Best-effort — the backend will also timeout the session independently
    }

    setState((prev) => ({ ...prev, phase: "completed" }));
  }, [state.sessionId, stopTimer]);

  // Watch for timer hitting zero
  useEffect(() => {
    if (state.timeRemaining === 0 && state.phase === "active") {
      handleTimeout();
    }
  }, [state.timeRemaining, state.phase, handleTimeout]);

  const setCurrentFile = useCallback((filename: string) => {
    setState((prev) => ({ ...prev, currentFile: filename }));
  }, []);

  return {
    ...state,
    startExam,
    submitAnswer,
    handleTimeout,
    setCurrentFile,
  };
}
```

### 5. Components

#### `src/app/exam/page.tsx` — The Exam Page

```typescript
"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, Suspense } from "react";
import { useExamState } from "@/hooks/useExamState";
import ExamLayout from "@/components/ExamLayout";
import CodePanel from "@/components/CodePanel";
import ExamPanel from "@/components/ExamPanel";
import CompletedScreen from "@/components/CompletedScreen";

const EXAM_DURATION = Number(process.env.NEXT_PUBLIC_EXAM_DURATION_SECONDS || 900);

function ExamContent() {
  const searchParams = useSearchParams();
  const studentId = searchParams.get("student_id");

  const exam = useExamState(EXAM_DURATION);

  useEffect(() => {
    if (studentId && exam.phase === "loading") {
      exam.startExam(studentId);
    }
  }, [studentId]); // intentionally not including exam to avoid re-triggers

  if (!studentId) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-950 text-white">
        <p className="text-xl">Missing student_id parameter.</p>
      </div>
    );
  }

  if (exam.phase === "loading") {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-950 text-white">
        <p className="text-xl animate-pulse">Loading exam…</p>
      </div>
    );
  }

  if (exam.phase === "error") {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-950 text-white">
        <div className="text-center">
          <p className="text-xl text-red-400 mb-2">Error</p>
          <p className="text-gray-400">{exam.error}</p>
        </div>
      </div>
    );
  }

  if (exam.phase === "completed") {
    return <CompletedScreen />;
  }

  return (
    <ExamLayout>
      <CodePanel
        files={exam.files}
        currentFile={exam.currentFile}
        action={exam.action}
        onFileSelect={exam.setCurrentFile}
        assignmentName={exam.assignmentName}
      />
      <ExamPanel
        questionText={exam.questionText}
        questionNumber={exam.questionNumber}
        timeRemaining={exam.timeRemaining}
        isSubmitting={exam.isSubmitting}
        onSubmit={exam.submitAnswer}
      />
    </ExamLayout>
  );
}

export default function ExamPage() {
  return (
    <Suspense fallback={<div className="h-screen bg-gray-950" />}>
      <ExamContent />
    </Suspense>
  );
}
```

#### `src/components/ExamLayout.tsx`

A full-viewport CSS grid with two equal panels separated by a thin divider.

```typescript
export default function ExamLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen w-screen grid grid-cols-2 bg-gray-950 overflow-hidden">
      {children}
    </div>
  );
}
```

#### `src/components/CodePanel.tsx`

Contains the file tab bar and Monaco editor.

Props:
- `files: Record<string, string>`
- `currentFile: string | null`
- `action: ExamAction | null`
- `onFileSelect: (filename: string) => void`
- `assignmentName: string` — displayed as a header above the file tabs (e.g., "Assignment 3: Virtual Memory")

Renders the `assignmentName` as a small header/label at the top, then `<FileTabBar>` below it, and `<CodeViewer>` filling the remaining height.

#### `src/components/FileTabBar.tsx`

A horizontal scrollable bar of filename tabs. The active tab is highlighted. Clicking a tab calls `onFileSelect`.

Props:
- `filenames: string[]`
- `activeFile: string | null`
- `onSelect: (filename: string) => void`

#### `src/components/CodeViewer.tsx` — Monaco Editor Integration

This is the most complex component. It wraps `@monaco-editor/react` in read-only mode.

Props:
- `code: string` — the content of the currently selected file
- `filename: string` — used to infer language (`.c` → C, `.py` → Python, `.h` → C, `.java` → Java)
- `highlightLine: number | null` — line to scroll to and highlight

Implementation details:

```typescript
"use client";

import { useRef, useEffect } from "react";
import Editor, { type Monaco } from "@monaco-editor/react";
import type { editor } from "monaco-editor";

interface CodeViewerProps {
  code: string;
  filename: string;
  highlightLine: number | null;
}

function inferLanguage(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase();
  const map: Record<string, string> = {
    c: "c", h: "c", cpp: "cpp", hpp: "cpp",
    py: "python", java: "java", js: "javascript",
    ts: "typescript", rs: "rust", go: "go",
    sh: "shell", bash: "shell", makefile: "makefile",
    md: "markdown", txt: "plaintext",
  };
  return map[ext || ""] || "plaintext";
}

export default function CodeViewer({ code, filename, highlightLine }: CodeViewerProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const decorationsRef = useRef<editor.IEditorDecorationsCollection | null>(null);

  function handleEditorMount(editor: editor.IStandaloneCodeEditor, monaco: Monaco) {
    editorRef.current = editor;

    // Define the highlight style
    monaco.editor.defineTheme("exam-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [],
      colors: {
        "editor.background": "#0a0a0f",
      },
    });
    monaco.editor.setTheme("exam-dark");
  }

  useEffect(() => {
    const editor = editorRef.current;
    if (!editor) return;

    // Clear previous decorations
    if (decorationsRef.current) {
      decorationsRef.current.clear();
      decorationsRef.current = null;
    }

    if (highlightLine && highlightLine > 0) {
      // Scroll to the line
      editor.revealLineInCenter(highlightLine);

      // Add a yellow highlight decoration
      decorationsRef.current = editor.createDecorationsCollection([
        {
          range: {
            startLineNumber: highlightLine,
            startColumn: 1,
            endLineNumber: highlightLine,
            endColumn: 1,
          },
          options: {
            isWholeLine: true,
            className: "highlight-line",
            glyphMarginClassName: "highlight-glyph",
          },
        },
      ]);
    }
  }, [highlightLine, code]); // re-run when line changes or file content changes

  return (
    <div className="flex-1 overflow-hidden">
      <Editor
        height="100%"
        language={inferLanguage(filename)}
        value={code}
        theme="exam-dark"
        onMount={handleEditorMount}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 15,
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          wordWrap: "on",
          domReadOnly: true,
          contextmenu: false, // disable right-click menu in kiosk
          // Disable features students don't need
          find: { addExtraSpaceOnTop: false },
          folding: false,
        }}
      />
    </div>
  );
}
```

**Add to `globals.css`:**
```css
.highlight-line {
  background-color: rgba(250, 204, 21, 0.2) !important;  /* yellow-400 at 20% */
  border-left: 3px solid #facc15 !important;
}
```

#### `src/components/ExamPanel.tsx`

The right panel containing the timer, question, and answer input.

Props:
- `questionText: string`
- `questionNumber: number`
- `timeRemaining: number`
- `isSubmitting: boolean`
- `onSubmit: (answer: string) => void`

This component owns a local `answerText` state (the textarea content) which it clears after successful submission.

#### `src/components/Timer.tsx`

Displays `MM:SS` countdown. Turns red when under 60 seconds.

Props:
- `secondsRemaining: number`

```typescript
export default function Timer({ secondsRemaining }: { secondsRemaining: number }) {
  const minutes = Math.floor(secondsRemaining / 60);
  const seconds = secondsRemaining % 60;
  const isLow = secondsRemaining < 60;

  return (
    <div className={`font-mono text-2xl font-bold tabular-nums ${isLow ? "text-red-400 animate-pulse" : "text-gray-300"}`}>
      {String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}
    </div>
  );
}
```

#### `src/components/QuestionDisplay.tsx`

Renders the current question in a styled container. Shows `Question {n} of 3` as a label.

Props:
- `questionText: string`
- `questionNumber: number`

#### `src/components/AnswerInput.tsx`

A textarea and submit button. The submit button is disabled while `isSubmitting` is true. The textarea is auto-focused after each new question appears.

Props:
- `isSubmitting: boolean`
- `onSubmit: (text: string) => void`

The component manages its own `value` state for the textarea and clears it on submit.

#### `src/components/CompletedScreen.tsx`

A full-screen message: "Exam Complete — Please notify the proctor." No further actions available. Clean, centered, large text.

### 6. Styling Notes

- **Dark theme throughout** (gray-950 background). This is an exam in a lab — dark theme reduces eye strain and looks serious.
- **No unnecessary UI chrome** — no header, no sidebar, no navigation. Pure functional layout.
- **The code panel border**: a subtle 1px `gray-800` border between the two panels.
- **Question text**: rendered with `whitespace-pre-wrap` so the examiner's formatting is preserved. Use a readable serif or mono font for exam questions — e.g., `font-serif` class.
- **The submit button**: should be prominent — a solid blue/indigo button that shows a spinner when submitting.
- **Textarea**: large, filling available space in the right panel. Allow the student to write comfortably.
- **Timer**: positioned at the top-right of the exam panel, always visible.
- Right-click should be disabled throughout (`onContextMenu={(e) => e.preventDefault()}`).
- Text selection in the question display should be disabled (CSS `user-select: none`).
- For the overall layout, ensure it works well on 1920×1080 (standard kiosk resolution) and 2560×1440 (if dual-monitor setup splits the panels).

### 7. Root Layout

`src/app/layout.tsx`:

```typescript
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OS Oral Exam",
  description: "Automated oral examination system",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-gray-950 text-gray-100 overflow-hidden">
        {children}
      </body>
    </html>
  );
}
```

### 8. `globals.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Kiosk overrides */
html, body {
  overflow: hidden;
  height: 100vh;
  width: 100vw;
  margin: 0;
  padding: 0;
  /* Prevent text selection in non-input areas */
  -webkit-user-select: none;
  user-select: none;
}

/* Allow text selection only in textarea */
textarea {
  -webkit-user-select: text;
  user-select: text;
}

/* Monaco editor line highlight */
.highlight-line {
  background-color: rgba(250, 204, 21, 0.2) !important;
  border-left: 3px solid #facc15 !important;
}

.highlight-glyph {
  background-color: #facc15;
  width: 4px !important;
  margin-left: 3px;
}
```

### 9. `next.config.ts`

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone", // required for Docker/Cloud Run deployment
};

export default nextConfig;
```

### 10. Dockerfile

```dockerfile
FROM node:20-alpine AS base

# Install dependencies
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# Build
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Production
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=8080

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 8080
CMD ["node", "server.js"]
```

### 11. Deployment Instructions

**Prerequisites:**
- `gcloud` CLI authenticated with the `ai-examiner-system` project.
- A service account for the frontend: `exam-frontend@ai-examiner-system.iam.gserviceaccount.com`.
- That SA has `roles/run.invoker` on the backend Cloud Run service.

**Steps:**

```bash
# 1. Create the service account (if not already done)
gcloud iam service-accounts create exam-frontend \
  --display-name="Exam Frontend" \
  --project=ai-examiner-system

# 2. Grant it permission to invoke the backend Cloud Run service
gcloud run services add-iam-policy-binding ai-examiner-backend \
  --member="serviceAccount:exam-frontend@ai-examiner-system.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=me-west1 \
  --project=ai-examiner-system

# 3. Build and deploy.
gcloud run deploy exam-frontend \
  --source=. \
  --region=me-west1 \
  --project=ai-examiner-system \
  --service-account=exam-frontend@ai-examiner-system.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --set-env-vars="BACKEND_URL=https://ai-examiner-backend-XXXXX-me-west1.a.run.app,EXAM_DURATION_SECONDS=900,NEXT_PUBLIC_EXAM_DURATION_SECONDS=900" \
  --port=8080 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10
```

**Note**: The frontend Cloud Run service uses `--allow-unauthenticated` because kiosk browsers need to reach it without credentials. This is safe because:
1. The frontend only exposes student endpoints (start, answer, timeout).
2. Admin endpoints are not proxied.
3. The frontend-to-backend communication is secured via IAM (service account identity tokens).
4. The exam room is physically controlled and proctored.

**Recommended**: Apply a network restriction (Cloud Armor policy or university firewall rules) to limit frontend access to the exam room's IP range. See the "Authentication & Security Design" section in Part 1 for details.

### 12. Local Development

```bash
# 1. Install dependencies
npm install

# 2. Set up environment
cp .env.local.example .env.local
# Edit .env.local: set BACKEND_URL and GOOGLE_SA_KEY_JSON
# For GOOGLE_SA_KEY_JSON, download the SA key JSON from GCP Console
# and paste its contents as a single line.

# 3. Run dev server
npm run dev

# 4. Open browser
# http://localhost:3000/exam?student_id=test-student-123
```

### 13. package.json Dependencies

```json
{
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@monaco-editor/react": "^4.6.0",
    "google-auth-library": "^9.0.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "@types/node": "^20.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

### 14. Summary of API Call Flow

```
1. TA navigates kiosk to /exam?student_id=12345
2. ExamPage reads student_id from URL params
3. useExamState.startExam("12345") is called
4. Browser → POST /api/exam/start { student_id: "12345" }
5. Next.js API route → mints ID token → POST backend/api/auth/start
6. Response: { session_id, assignment_name, question_text, files, action, ... }
7. State: phase="active", files loaded, Q1 displayed, timer starts
8. Code viewer shows first file (or action_file if JUMP_TO_LINE)
9. Student types answer, clicks Submit
10. Browser → POST /api/exam/answer { session_id, answer_text }
11. Next.js API route → proxies to backend → response with Q2
12. If action="JUMP_TO_LINE": switch file tab, scroll, highlight line
13. Repeat for Q3
14. If is_complete=true or timer hits 0: phase="completed"
15. Timeout: Browser → POST /api/exam/timeout { session_id }
16. CompletedScreen shown — exam is over
```

### 15. Edge Cases to Handle

- **Double submit prevention**: Disable the submit button and textarea while `isSubmitting` is true.
- **Network errors**: Show an error message but don't crash. The proctor can refresh the page. The backend should handle session recovery (re-calling start with the same student_id should resume, not restart).
- **Timer continues during API calls**: The timer runs client-side independently. If an API call takes 5 seconds, the timer still counts down. This is correct — the exam is time-limited.
- **Browser refresh**: The exam state is lost. The TA must navigate back to the URL. The backend should handle re-starts gracefully (return current state if session exists).
- **Large files**: Monaco handles large files well, but if a student submitted a 10,000-line file, consider setting `editor.setScrollTop()` rather than `revealLineInCenter()` for smoother UX. In practice, university OS assignments are typically under 500 lines.
- **File tab overflow**: If a student has 10+ files, the tab bar should be horizontally scrollable.

---

This is the complete specification. Build all files, ensure they compile with `npm run build`, and verify the development server starts with `npm run dev`. Use placeholder data for the backend response during development if the actual backend is not available.
