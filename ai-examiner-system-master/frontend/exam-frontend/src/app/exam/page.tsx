"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useExamState } from "@/hooks/useExamState";
import EntryScreen from "@/components/EntryScreen";
import WelcomeScreen from "@/components/WelcomeScreen";
import PreferencesScreen from "@/components/PreferencesScreen";
import RosterConfirmScreen from "@/components/RosterConfirmScreen";
import ExamLayout from "@/components/ExamLayout";
import CodePanel from "@/components/CodePanel";
import ExamPanel from "@/components/ExamPanel";
import CompletedScreen from "@/components/CompletedScreen";
import AssignmentConfirmScreen from "@/components/AssignmentConfirmScreen";
import type { Gender, Language } from "@/lib/welcomeStrings";
import { UI_LOADING_EXAM, UI_ERROR_TITLE, UI_BACK_TO_ENTRY, t } from "@/lib/uiStrings";
import type { AssignmentOption } from "@/lib/types";
import type { IdentityMode, SubmissionKind } from "@/lib/courseStrings";

const DEFAULT_EXAM_DURATION = Number(process.env.NEXT_PUBLIC_EXAM_DURATION_SECONDS ?? 960);

// What a student identifies with, and the course name — per deployment, so they come from
// the backend at runtime rather than a build arg (one frontend image serves every course).
interface ExamConfig {
  identity_mode: IdentityMode;
  submission_kind: SubmissionKind;
  course_title_he: string;
  assignments: AssignmentOption[];
}

const FALLBACK_CONFIG: ExamConfig = {
  identity_mode: "github_username",
  submission_kind: "code",
  course_title_he: "מערכות הפעלה — הערכת ידע ומיומנות בתרגילים",
  assignments: [],
};

function ExamContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // QA mode: params passed via URL
  const urlGithub     = searchParams.get("github_username") ?? undefined;
  const urlAssignment = searchParams.get("assignment_name") ?? undefined;
  const urlPersona    = searchParams.get("persona")         ?? undefined;
  const isQAMode      = !!(urlGithub && urlAssignment);

  // In QA mode, ?exam_duration=N overrides the timer (minimum 30 s)
  const urlDuration = searchParams.get("exam_duration");
  const EXAM_DURATION = (isQAMode && urlDuration) ? Math.max(30, Number(urlDuration)) : DEFAULT_EXAM_DURATION;
  const EXAM_DURATION_MINUTES = Math.round(EXAM_DURATION / 60);

  const exam = useExamState(EXAM_DURATION);

  // Null until resolved: the entry screen must not flash "GitHub username" at a student
  // who is about to type an ID. Any failure falls back rather than blocking entry.
  const [config, setConfig] = useState<ExamConfig | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/config")
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setConfig({ ...FALLBACK_CONFIG, ...d }); })
      .catch(() => { if (!cancelled) setConfig(FALLBACK_CONFIG); });
    return () => { cancelled = true; };
  }, []);

  // Language is known after PreferencesScreen; default to "he" for early screens
  const lang: Language = exam.language ?? "he";

  // In QA mode, reset navigates back to /qa instead of re-entering the same exam
  function handleReset() {
    exam.reset();
    if (isQAMode) router.push("/qa");
  }

  // ── Phase: entry ────────────────────────────────────────────────────────────
  if (exam.phase === "entry") {
    // QA shortcut: URL params present → skip roster flow
    if (urlGithub && urlAssignment) {
      return (
        <WelcomeScreen
          onStart={() => exam.startExam(urlGithub, urlAssignment, urlPersona, "he")}
          examDurationMinutes={EXAM_DURATION_MINUTES}
          gender="male"
          language="he"
        />
      );
    }
    if (!config) return <div className="h-screen bg-gray-950" />;
    return (
      <EntryScreen
        onSubmit={exam.lookupRoster}
        isLoading={false}
        error={exam.error}
        identityMode={config.identity_mode}
        courseTitle={config.course_title_he}
      />
    );
  }

  // ── Phase: roster_lookup ────────────────────────────────────────────────────
  if (exam.phase === "roster_lookup") {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-gray-950 text-white">
        <p className="text-xl animate-pulse" dir="rtl">מאחזר את המטלה שהוגשה…</p>
      </div>
    );
  }

  // ── Phase: assignment_confirm ───────────────────────────────────────────────
  if (exam.phase === "assignment_confirm") {
    const detected = exam.availableAssignments?.find((a) => a.name === exam.pendingAssignment)
      ?? { name: exam.pendingAssignment ?? "", label_he: exam.pendingAssignmentLabelHe ?? "", label_en: exam.pendingAssignmentLabelEn ?? "" };
    // Fallback list comes from the backend registry, which is course-scoped — hardcoding
    // it here once offered the three OS assignments to a Linear Algebra student. A course
    // with one assignment yields one entry, and the chooser hides itself.
    const allOptions = (exam.availableAssignments && exam.availableAssignments.length >= 2)
      ? exam.availableAssignments
      : (config ?? FALLBACK_CONFIG).assignments;
    return (
      <AssignmentConfirmScreen
        detectedAssignment={detected}
        availableAssignments={allOptions}
        isLoading={false}
        onConfirm={exam.confirmAssignment}
        onBack={handleReset}
      />
    );
  }

  // ── Phase: roster_confirm ───────────────────────────────────────────────────
  if (exam.phase === "roster_confirm") {
    return (
      <RosterConfirmScreen
        githubUsername={exam.pendingGithub ?? ""}
        assignmentName={exam.pendingAssignment ?? ""}
        onConfirm={(github) => exam.confirmRoster(github)}
        onBack={handleReset}
        identityMode={(config ?? FALLBACK_CONFIG).identity_mode}
        submissionKind={(config ?? FALLBACK_CONFIG).submission_kind}
      />
    );
  }

  // ── Phase: preferences ──────────────────────────────────────────────────────
  if (exam.phase === "preferences") {
    return (
      <PreferencesScreen
        onConfirm={(gender: Gender, language: Language) =>
          exam.setPreferences(gender, language)
        }
      />
    );
  }

  // ── Phase: briefing ─────────────────────────────────────────────────────────
  if (exam.phase === "briefing") {
    return (
      <WelcomeScreen
        onStart={() =>
          exam.startExam(
            exam.pendingGithub!,
            exam.pendingAssignment ?? undefined,
            undefined,
            exam.language ?? "he",
          )
        }
        examDurationMinutes={EXAM_DURATION_MINUTES}
        gender={exam.gender ?? "male"}
        language={lang}
        assignmentLabel={lang === "en" ? (exam.pendingAssignmentLabelEn ?? undefined) : (exam.pendingAssignmentLabelHe ?? undefined)}
      />
    );
  }

  // ── Phase: loading ──────────────────────────────────────────────────────────
  if (exam.phase === "loading") {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-gray-950 text-white">
        <p className="text-xl animate-pulse" dir={lang === "en" ? "ltr" : "rtl"}>{t(UI_LOADING_EXAM, lang)}</p>
      </div>
    );
  }

  // ── Phase: error ────────────────────────────────────────────────────────────
  if (exam.phase === "error") {
    const dir = lang === "en" ? "ltr" : "rtl";
    return (
      <div className="h-screen flex items-center justify-center bg-gray-950 text-white">
        <div className="text-center space-y-4" dir={dir}>
          <p className="text-xl text-red-400">{t(UI_ERROR_TITLE, lang)}</p>
          <p className="text-gray-400">{exam.error}</p>
          <button
              onClick={handleReset}
              className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition-colors"
            >
              {t(UI_BACK_TO_ENTRY, lang)}
            </button>
        </div>
      </div>
    );
  }

  // ── Phase: distress ─────────────────────────────────────────────────────────
  if (exam.phase === "distress") {
    return (
      <CompletedScreen
        onReset={handleReset}
        sessionId={exam.sessionId ?? undefined}
        isDistress
        distressMessage={exam.distressMessage ?? undefined}
        language={lang}
      />
    );
  }

  // ── Phase: completed ────────────────────────────────────────────────────────
  if (exam.phase === "completed") {
    return (
      <CompletedScreen
        onReset={handleReset}
        sessionId={exam.sessionId ?? undefined}
        githubUsername={urlGithub}
        persona={exam.persona ?? undefined}
        isTimeout={exam.timedOut}
        language={lang}
      />
    );
  }

  // ── Phase: active ───────────────────────────────────────────────────────────
  return (
    <ExamLayout>
      <CodePanel
        files={exam.files}
        currentFile={exam.currentFile}
        action={exam.action}
        scrollRevision={exam.scrollRevision}
        onFileSelect={exam.setCurrentFile}
        assignmentName={exam.assignmentName}
        submissionKind={(config ?? FALLBACK_CONFIG).submission_kind}
      />
      <ExamPanel
        questionText={exam.questionText}
        questionNumber={exam.questionNumber}
        timeRemaining={exam.timeRemaining}
        isSubmitting={exam.isSubmitting}
        onSubmit={exam.submitAnswer}
        error={exam.error}
        sessionId={exam.sessionId ?? undefined}
        language={lang}
        onComplaintSubmitted={handleReset}
        registerAnswerGetter={exam.registerAnswerGetter}
        submissionKind={(config ?? FALLBACK_CONFIG).submission_kind}
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
