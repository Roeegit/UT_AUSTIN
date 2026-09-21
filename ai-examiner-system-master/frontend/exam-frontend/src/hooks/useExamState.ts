"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import type { ExamPhase, ExamAction, ExamStartResponse, ExamAnswerResponse, TranscriptEntry, AssignmentOption } from "@/lib/types";
import type { Gender, Language } from "@/lib/welcomeStrings";

// Shown on an early server error (5xx), which is almost always a cold start — the server was
// idle and is spinning up. Reassures the student instead of showing a raw error.
const COLD_START_MSG = "נראה שהשרת מתעורר (ייתכן עיכוב קצר בשימוש הראשון). אנא המתן 2-3 שניות ונסה שוב.";

interface ExamState {
  phase: ExamPhase;
  sessionId: string | null;
  assignmentName: string;
  files: Record<string, string>;
  currentFile: string | null;
  questionText: string;
  questionNumber: number;
  action: ExamAction | null;
  /** Increments each time a new JUMP_TO_LINE action arrives — drives auto-scroll in CodeViewer */
  scrollRevision: number;
  timeRemaining: number;
  isSubmitting: boolean;
  error: string | null;
  transcript: TranscriptEntry[];
  persona: string | null;
  timedOut: boolean;
  /** The examiner's compassionate closing message when END_EXAM_DISTRESS is triggered */
  distressMessage: string | null;
  // ── Pre-exam flow state ─────────────────────────────────────────────────
  pendingGithub: string | null;
  pendingAssignment: string | null;
  pendingAssignmentLabelHe: string | null;
  pendingAssignmentLabelEn: string | null;
  availableAssignments: AssignmentOption[] | null;
  gender: Gender | null;
  language: Language | null;
}

export function useExamState(examDurationSeconds: number) {
  const [state, setState] = useState<ExamState>({
    phase: "entry",
    sessionId: null,
    assignmentName: "",
    files: {},
    currentFile: null,
    questionText: "",
    questionNumber: 1,
    action: null,
    scrollRevision: 0,
    timeRemaining: examDurationSeconds,
    isSubmitting: false,
    error: null,
    transcript: [],
    persona: null,
    timedOut: false,
    distressMessage: null,
    pendingGithub: null,
    pendingAssignment: null,
    pendingAssignmentLabelHe: null,
    pendingAssignmentLabelEn: null,
    availableAssignments: null,
    gender: null,
    language: null,
  });

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const examStartTimeRef = useRef<number | null>(null); // wall-clock ms when exam started
  // While the student waits for the AI (after Submit, until the next question
  // appears) the clock freezes. We record when the pause began; on resume we shift
  // examStartTimeRef forward by the paused duration so that wall-clock-based
  // elapsed never counts the wait. null = not paused.
  const pauseStartRef = useRef<number | null>(null);
  // Effective duration for this session — overridden by server response for accommodation students
  const sessionDurationRef = useRef<number>(examDurationSeconds);
  // Use a ref to track sessionId inside timer callback without stale closure
  const sessionIdRef = useRef<string | null>(null);
  const phaseRef = useRef<ExamPhase>("loading");
  const answerGetterRef = useRef<() => string>(() => "");

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    pauseStartRef.current = null;
  }, []);

  // Freeze the clock (student is waiting for the AI response).
  const pauseTimer = useCallback(() => {
    if (pauseStartRef.current === null) {
      pauseStartRef.current = Date.now();
    }
  }, []);

  // Resume: push the start time forward by however long we were paused, so the
  // elapsed calculation skips the wait entirely and the display picks up where it left off.
  const resumeTimer = useCallback(() => {
    if (pauseStartRef.current !== null) {
      if (examStartTimeRef.current !== null) {
        examStartTimeRef.current += Date.now() - pauseStartRef.current;
      }
      pauseStartRef.current = null;
    }
  }, []);

  const registerAnswerGetter = useCallback((getter: () => string) => {
    answerGetterRef.current = getter;
  }, []);

  const handleTimeout = useCallback(async () => {
    stopTimer();
    const sid = sessionIdRef.current;
    if (sid) {
      try {
        const partial = answerGetterRef.current().trim();
        await fetch("/api/exam/timeout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sid, partial_answer: partial || undefined }),
        });
      } catch {
        // best-effort
      }
    }
    setState((prev) => ({ ...prev, phase: "completed", timedOut: true }));
    phaseRef.current = "completed";
  }, [stopTimer]);

  const startTimer = useCallback(() => {
    stopTimer();
    examStartTimeRef.current = Date.now();
    const duration = sessionDurationRef.current;
    timerRef.current = setInterval(() => {
      // Frozen while the student waits for the AI — hold the displayed value steady.
      if (pauseStartRef.current !== null) return;
      const elapsed = Math.floor((Date.now() - (examStartTimeRef.current ?? Date.now())) / 1000);
      const remaining = Math.max(0, duration - elapsed);
      setState((prev) => ({ ...prev, timeRemaining: remaining }));
    }, 500); // tick every 500ms so it never visually lags by more than half a second
  }, [stopTimer]);

  useEffect(() => {
    return () => stopTimer();
  }, [stopTimer]);

  // Watch for timer hitting zero
  useEffect(() => {
    if (state.timeRemaining === 0 && state.phase === "active") {
      handleTimeout();
    }
  }, [state.timeRemaining, state.phase, handleTimeout]);

  const reset = useCallback(() => {
    stopTimer();
    sessionIdRef.current = null;
    examStartTimeRef.current = null;
    sessionDurationRef.current = examDurationSeconds;
    phaseRef.current = "entry";
    setState({
      phase: "entry",
      sessionId: null,
      assignmentName: "",
      files: {},
      currentFile: null,
      questionText: "",
      questionNumber: 1,
      action: null,
      scrollRevision: 0,
      timeRemaining: examDurationSeconds,
      isSubmitting: false,
      error: null,
      transcript: [],
      persona: null,
      timedOut: false,
      distressMessage: null,
      pendingGithub: null,
      pendingAssignment: null,
      pendingAssignmentLabelHe: null,
      pendingAssignmentLabelEn: null,
      availableAssignments: null,
      gender: null,
      language: null,
    });
  }, [stopTimer, examDurationSeconds]);

  /**
   * Called when student submits their GitHub username from EntryScreen.
   * Hits the lookup API to verify the assignment exists and check the one-time-use lock.
   */
  const lookupRoster = useCallback(async (githubUsername: string, assignmentOverride?: string) => {
    setState((prev) => ({ ...prev, phase: "roster_lookup", error: null }));
    phaseRef.current = "roster_lookup";
    try {
      const url = assignmentOverride
        ? `/api/exam/lookup/${encodeURIComponent(githubUsername)}?assignment_name=${encodeURIComponent(assignmentOverride)}`
        : `/api/exam/lookup/${encodeURIComponent(githubUsername)}`;
      const res = await fetch(url);
      let data: { found?: boolean; locked?: boolean; assignment_name?: string; assignment_label_he?: string; assignment_label_en?: string; available_assignments?: AssignmentOption[]; error?: string } = {};
      try {
        data = await res.json();
      } catch {
        // 5xx typically returns a non-JSON error page — almost always a cold start here.
        const msg = res.status >= 500 ? COLD_START_MSG : `שגיאת שרת (${res.status}) — נסה שוב.`;
        setState((prev) => ({ ...prev, phase: "entry", error: msg }));
        phaseRef.current = "entry";
        return;
      }
      if (!res.ok || !data.found) {
        const errMsg = res.status >= 500
          ? COLD_START_MSG
          : data.error
          ? `שגיאה (${res.status}): ${data.error}`
          : "לא נמצאה הגשה עבור שם המשתמש הזה. בדוק את השם ונסה שוב.";
        setState((prev) => ({ ...prev, phase: "entry", error: errMsg }));
        phaseRef.current = "entry";
        return;
      }
      if (data.locked) {
        const errMsg = data.error === "complaint_pending"
          ? "קיימת פנייה פתוחה עבור שם משתמש זה. לא ניתן להתחיל הערכה עד שהסגל האקדמי יטפל בפנייה ויאשר המשך."
          : "שם המשתמש הזה כבר שומש. אנא פנה לסגל האקדמי.";
        setState((prev) => ({ ...prev, phase: "entry", error: errMsg }));
        phaseRef.current = "entry";
        return;
      }
      setState((prev) => ({
        ...prev,
        phase: "assignment_confirm",
        pendingGithub: githubUsername,
        pendingAssignment: data.assignment_name ?? null,
        pendingAssignmentLabelHe: data.assignment_label_he ?? null,
        pendingAssignmentLabelEn: data.assignment_label_en ?? null,
        availableAssignments: data.available_assignments ?? null,
        error: null,
      }));
      phaseRef.current = "assignment_confirm";
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setState((prev) => ({ ...prev, phase: "entry", error: `שגיאת רשת — ${msg}` }));
      phaseRef.current = "entry";
    }
  }, []);

  /**
   * Called from AssignmentConfirmScreen.
   * If the student confirmed the detected assignment, advance to roster_confirm.
   * If they switched to a different one, re-run the lookup with the override.
   */
  const confirmAssignment = useCallback((chosenAssignment: string) => {
    setState((prev) => {
      if (prev.pendingAssignment === chosenAssignment) {
        phaseRef.current = "roster_confirm";
        return { ...prev, phase: "roster_confirm" };
      }
      // Switch — re-trigger lookup with the override (async, handled outside setState)
      return prev;
    });
    setState((prev) => {
      if (prev.pendingAssignment !== chosenAssignment && prev.pendingGithub) {
        // Kick off a new lookup with the override; lookupRoster will update state
        lookupRoster(prev.pendingGithub, chosenAssignment);
      }
      return prev;
    });
  }, [lookupRoster]);

  /** Called when student confirms their GitHub username from RosterConfirmScreen. */
  const confirmRoster = useCallback((githubUsername: string) => {
    setState((prev) => ({
      ...prev,
      phase: "preferences",
      pendingGithub: githubUsername,
    }));
    phaseRef.current = "preferences";
  }, []);

  /** Called when student picks gender + language from PreferencesScreen. */
  const setPreferences = useCallback((gender: Gender, language: Language) => {
    setState((prev) => ({ ...prev, gender, language, phase: "briefing" }));
    phaseRef.current = "briefing";
  }, []);

  const startExam = useCallback(
    async (
      githubUsername: string,
      assignmentName?: string,
      persona?: string,
      language?: string,
    ) => {
      setState((prev) => ({ ...prev, phase: "loading" }));
      phaseRef.current = "loading";
      try {
        const res = await fetch("/api/exam/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            github_username: githubUsername,
            assignment_name: assignmentName || null,
            persona,
            language: language ?? "he",
          }),
        });

        let data: ExamStartResponse & { error?: string; detail?: string };
        try {
          data = await res.json();
        } catch {
          // Non-JSON 5xx page — almost always a cold start.
          const msg = res.status >= 500 ? COLD_START_MSG : `Start failed (${res.status})`;
          setState((prev) => ({ ...prev, phase: "error", error: msg }));
          phaseRef.current = "error";
          return;
        }

        if (!res.ok) {
          const detail = data.detail || data.error || "";
          const errMsg = detail === "already_started"
            ? "שם המשתמש הזה כבר שומש. אנא פנה לסגל האקדמי."
            : detail === "complaint_pending"
            ? "קיימת פנייה פתוחה עבור שם משתמש זה. לא ניתן להתחיל הערכה עד שהסגל האקדמי יטפל בפנייה ויאשר המשך."
            : res.status >= 500
            ? COLD_START_MSG
            : detail || `Start failed (${res.status})`;
          setState((prev) => ({ ...prev, phase: "error", error: errMsg }));
          phaseRef.current = "error";
          return;
        }

        const fileNames = Object.keys(data.files || {});
        const initialFile =
          data.action === "JUMP_TO_LINE" && data.action_file
            ? data.action_file
            : fileNames[0] || null;

        sessionIdRef.current = data.session_id;
        phaseRef.current = "active";

        // Apply per-student duration (accommodation students may have extended time)
        const effectiveDuration = data.exam_duration_seconds ?? examDurationSeconds;
        sessionDurationRef.current = effectiveDuration;

        const firstQuestion: TranscriptEntry = {
          questionNumber: data.question_number ?? 1,
          questionText: data.question_text,
          answerText: "",
        };

        setState((prev) => ({
          ...prev,
          phase: "active",
          sessionId: data.session_id,
          assignmentName: data.assignment_name || assignmentName || "",
          files: data.files || {},
          currentFile: initialFile,
          questionText: data.question_text,
          questionNumber: data.question_number ?? 1,
          action:
            data.action === "JUMP_TO_LINE"
              ? { type: data.action, file: data.action_file, codeLine: data.action_code_line }
              : null,
          scrollRevision: data.action === "JUMP_TO_LINE" ? prev.scrollRevision + 1 : prev.scrollRevision,
          transcript: [firstQuestion],
          persona: persona ?? null,
          timeRemaining: effectiveDuration,
        }));

        startTimer();
      } catch {
        setState((prev) => ({
          ...prev,
          phase: "error",
          error: "Network error — could not reach exam server.",
        }));
        phaseRef.current = "error";
      }
    },
    [startTimer]
  );

  const submitAnswer = useCallback(
    async (answerText: string) => {
      if (!state.sessionId || state.isSubmitting) return;

      // Freeze the clock the instant Submit is pressed — it stays frozen until the
      // next question appears (or resumes if the submit fails and they can retry).
      pauseTimer();
      setState((prev) => ({ ...prev, isSubmitting: true }));

      try {
        const res = await fetch("/api/exam/answer", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: state.sessionId, answer_text: answerText }),
        });

        const data: ExamAnswerResponse & { error?: string; detail?: string } = await res.json();

        if (!res.ok) {
          resumeTimer(); // submit failed — student stays on this question, clock runs again
          setState((prev) => ({
            ...prev,
            isSubmitting: false,
            error: data.detail || data.error || "Failed to submit answer",
          }));
          return;
        }

        if (data.finished) {
          stopTimer();
          const nextPhase = data.distress_ended ? "distress" : "completed";
          phaseRef.current = nextPhase;
          setState((prev) => {
            // Update the last transcript entry (the one currently being answered).
            // Using index avoids overwriting earlier entries when a question is re-asked.
            const updatedTranscript = prev.transcript.map((entry, idx) =>
              idx === prev.transcript.length - 1 ? { ...entry, answerText } : entry
            );
            if (!data.distress_ended) {
              try {
                sessionStorage.setItem("qa_transcript", JSON.stringify(updatedTranscript));
              } catch {
                // sessionStorage may be unavailable (private browsing, etc.) — ignore
              }
            }
            return {
              ...prev,
              isSubmitting: false,
              phase: nextPhase,
              transcript: updatedTranscript,
              distressMessage: data.distress_ended ? (data.question_text ?? null) : null,
            };
          });
          return;
        }

        // Next question (or re-ask) is here — resume the clock.
        resumeTimer();
        setState((prev) => {
          // Fill in the answer for the last entry only (avoids overwriting earlier re-ask entries).
          const updatedTranscript = prev.transcript.map((entry, idx) =>
            idx === prev.transcript.length - 1 ? { ...entry, answerText } : entry
          );

          // Add entry for the next question
          const nextQuestionNumber = data.question_number ?? prev.questionNumber + 1;
          const nextEntry: TranscriptEntry = {
            questionNumber: nextQuestionNumber,
            questionText: data.question_text || "",
            answerText: "",
          };

          const hasNewAction = data.action === "JUMP_TO_LINE";
          // RE_ASK returns action=null and keeps the same question_number.
          // Any other outcome (NONE, JUMP_TO_LINE, or number advancing) means new content.
          const isNewQuestion = data.action != null || nextQuestionNumber !== prev.questionNumber;
          return {
            ...prev,
            isSubmitting: false,
            questionText: isNewQuestion ? (data.question_text || prev.questionText) : prev.questionText,
            error: isNewQuestion ? null : (data.question_text || prev.error),
            questionNumber: nextQuestionNumber,
            currentFile:
              hasNewAction && data.action_file
                ? data.action_file
                : prev.currentFile,
            action: hasNewAction
              ? { type: data.action!, file: data.action_file, codeLine: data.action_code_line }
              : prev.action,
            scrollRevision: hasNewAction ? prev.scrollRevision + 1 : prev.scrollRevision,
            transcript: [...updatedTranscript, nextEntry],
          };
        });
      } catch {
        resumeTimer(); // network error — student stays on this question, clock runs again
        setState((prev) => ({
          ...prev,
          isSubmitting: false,
          error: "Network error — could not submit answer.",
        }));
      }
    },
    [state.sessionId, state.isSubmitting, state.questionNumber, stopTimer, pauseTimer, resumeTimer]
  );

  const setCurrentFile = useCallback((filename: string) => {
    setState((prev) => ({ ...prev, currentFile: filename }));
  }, []);

  return {
    ...state,
    startExam,
    submitAnswer,
    handleTimeout,
    setCurrentFile,
    registerAnswerGetter,
    reset,
    lookupRoster,
    confirmAssignment,
    confirmRoster,
    setPreferences,
  };
}
