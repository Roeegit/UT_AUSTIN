"use client";

import { notFound, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import type { QAResults, TranscriptEntry } from "@/lib/types";

if (process.env.NEXT_PUBLIC_QA_MODE !== "true") {
  // guard — actual check happens inside the component
}

const PERSONA_LABELS: Record<string, string> = {
  "confident-owner": "בעלים בטוח",
  "nervous-competent": "מסוגל אך עצבני",
  "partial-understanding": "הבנה חלקית",
  "copied-memorized": "העתיק ושינן",
  "full-gpt": "GPT מלא",
  "prompt-injection": "ניסיון הזרקת פרומפט",
  "silent": "שקט / תשובות מינימליות",
};

const STUDENT_LABELS: Record<string, string> = {
  "student-a": "סטודנט חזק",
  "student-b": "סטודנט בינוני",
  "student-c": "סטודנט חלש / GPT",
};

function ScoreDot({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-600">—</span>;
  const colors = ["", "bg-red-500", "bg-orange-500", "bg-yellow-500", "bg-lime-500", "bg-green-500"];
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`w-3 h-3 rounded-full inline-block ${colors[score] ?? "bg-gray-500"}`} />
      <span className="text-gray-300 tabular-nums">{score}/5</span>
    </span>
  );
}

function ResultsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  if (process.env.NEXT_PUBLIC_QA_MODE !== "true") {
    notFound();
  }

  const studentId = searchParams.get("github_username") ?? "";
  const sessionId = searchParams.get("session_id") ?? "";
  const persona = searchParams.get("persona") ?? "";

  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [results, setResults] = useState<QAResults | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedSessionId, setCopiedSessionId] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load transcript from sessionStorage on mount
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("qa_transcript");
      if (raw) setTranscript(JSON.parse(raw));
    } catch {
      // ignore
    }
  }, []);

  // Poll for results every 5 seconds until complete
  useEffect(() => {
    if (!studentId) return;

    async function fetchResults() {
      try {
        const url = `/api/exam/results?github_username=${encodeURIComponent(studentId)}${sessionId ? `&session_id=${encodeURIComponent(sessionId)}` : ""}`;
        const res = await fetch(url);
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setPollError(body?.error ?? `שגיאה: ${res.status}`);
          return;
        }
        const data: QAResults = await res.json();
        setResults(data);
        setPollError(null);
        if (data.isComplete && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch {
        setPollError("שגיאת רשת בטעינת תוצאות");
      }
    }

    fetchResults();
    pollRef.current = setInterval(fetchResults, 5000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [studentId]);

  function buildPlainTextSummary(): string {
    const lines: string[] = [
      `תוצאות בחינה — ${studentId} (${STUDENT_LABELS[studentId] ?? studentId})`,
      `פרסונה: ${PERSONA_LABELS[persona] ?? persona}`,
      `סשן: ${sessionId}`,
      "",
    ];

    if (transcript.length > 0) {
      lines.push("=== שאלות ותשובות ===");
      transcript.forEach((entry, i) => {
        lines.push(`\nשאלה ${i + 1}: ${entry.questionText}`);
        lines.push(`תשובה: ${entry.answerText || "(ריק)"}`);
        if (results?.perQuestionScores?.[i] !== undefined) {
          lines.push(`ציון הבנה: ${results.perQuestionScores[i] ?? "—"}/5`);
        }
      });
      lines.push("");
    }

    if (results?.isComplete) {
      lines.push("=== ציונים ===");
      if (results.oralDefenseScore !== undefined)
        lines.push(`הגנה בעל פה: ${results.oralDefenseScore}`);
      if (results.codeQualityScore !== undefined)
        lines.push(`איכות קוד: ${results.codeQualityScore}`);
      if (results.finalGrade !== undefined)
        lines.push(`ציון סופי: ${JSON.stringify(results.finalGrade)}`);
    } else {
      lines.push("ציון מחושב... (בהמתנה)");
    }

    return lines.join("\n");
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(buildPlainTextSummary());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback: do nothing
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white py-10 px-4" dir="rtl">
      <div className="max-w-3xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white">תוצאות בחינה</h1>
            <p className="text-gray-400 mt-1">
              {STUDENT_LABELS[studentId] ?? studentId} &middot; פרסונה:{" "}
              <span className="text-indigo-300">{PERSONA_LABELS[persona] ?? persona}</span>
            </p>
            {sessionId && (
              <div className="flex items-center gap-2 mt-1">
                <span className="text-gray-500 text-xs">סשן:</span>
                <code className="text-xs text-indigo-300 bg-gray-800 px-2 py-0.5 rounded font-mono">{sessionId}</code>
                <button
                  onClick={() => { navigator.clipboard.writeText(sessionId); setCopiedSessionId(true); setTimeout(() => setCopiedSessionId(false), 2000); }}
                  className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                >
                  {copiedSessionId ? "✓" : "העתק"}
                </button>
              </div>
            )}
          </div>
          <div className="flex gap-3 flex-wrap">
            <button
              onClick={handleCopy}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-sm text-gray-200 rounded-lg transition-colors"
            >
              {copied ? "הועתק!" : "העתק תוצאות"}
            </button>
            <button
              onClick={() => router.push("/qa")}
              className="px-4 py-2 bg-indigo-700 hover:bg-indigo-600 text-sm text-white rounded-lg transition-colors"
            >
              התחל בדיקה חדשה
            </button>
          </div>
        </div>

        {/* Aggregate scores */}
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-200">
            {results?.isComplete ? "תוצאות הבדיקה" : "תשובות בבדיקה"}
          </h2>
          {pollError && results?.isComplete && (
            <p className="text-red-400 text-sm">{pollError}</p>
          )}
          {results?.isComplete ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="rounded-lg bg-gray-800 px-5 py-4 text-center">
                <p className="text-sm text-gray-400 mb-1">הגנה בעל פה</p>
                <p className="text-3xl font-bold text-white">
                  {results.oralDefenseScore !== undefined ? results.oralDefenseScore : "—"}
                </p>
              </div>
              <div className="rounded-lg bg-gray-800 px-5 py-4 text-center">
                <p className="text-sm text-gray-400 mb-1">איכות קוד</p>
                <p className="text-3xl font-bold text-white">
                  {results.codeQualityScore !== undefined ? results.codeQualityScore : "—"}
                </p>
              </div>
              <div className="rounded-lg bg-gray-800 px-5 py-4 text-center">
                <p className="text-sm text-gray-400 mb-1">ציון סופי</p>
                <p className="text-3xl font-bold text-indigo-300">
                  {results.finalGrade !== undefined
                    ? typeof results.finalGrade === "object"
                      ? JSON.stringify(results.finalGrade)
                      : String(results.finalGrade)
                    : "—"}
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 text-gray-400">
              <span className="w-5 h-5 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin inline-block" />
               ... אנא המתן בזמן שהמערכת מסיימת את הבדיקה.
            </div>
          )}
        </section>

        {/* Transcript */}
        {transcript.length > 0 && (
          <section className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-200">תמליל הבחינה</h2>
            {transcript.map((entry, i) => (
              <div
                key={i}
                className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-3"
              >
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <h3 className="text-sm font-semibold text-indigo-300">
                    שאלה {entry.questionNumber}
                  </h3>
                  {results?.perQuestionScores && (
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-gray-500">ציון גס:</span>
                      <ScoreDot score={results.perQuestionScores[i] ?? null} />
                    </div>
                  )}
                </div>
                <p className="text-gray-200 text-sm leading-relaxed" dir="auto">
                  {entry.questionText}
                </p>
                {entry.answerText && (
                  <div className="border-t border-gray-800 pt-3">
                    <p className="text-xs text-gray-500 mb-1">תשובת הסטודנט</p>
                    <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap" dir="auto">
                      {entry.answerText}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </section>
        )}

        {transcript.length === 0 && (
          <p className="text-gray-600 text-sm text-center py-6">
            לא נמצא תמליל — ייתכן שנוקה מה-sessionStorage.
          </p>
        )}
      </div>
    </div>
  );
}

export default function QAResultsPage() {
  return (
    <Suspense fallback={<div className="h-screen bg-gray-950" />}>
      <ResultsContent />
    </Suspense>
  );
}
