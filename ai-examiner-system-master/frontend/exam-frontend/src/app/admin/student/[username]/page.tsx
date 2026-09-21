"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import type { Language } from "@/lib/welcomeStrings";
import { AdminLangToggle, useAdminLang } from "@/lib/adminLang";
import {
  A_ANSWER, A_ANSWER_SWITCH, A_AUTHORSHIP_NOTE, A_BACK, A_CLOSE, A_CODE_QUALITY, A_CODE_REVIEW,
  A_DIFF_EASY, A_DIFF_HARD, A_DIFF_MEDIUM, A_EMAIL_MISSING, A_EMAIL_NOT_SENT, A_EMAIL_PREVIEW,
  A_EMAIL_SENT, A_EMAIL_SUBJECT, A_ERROR_N, A_FEEDBACK_ORAL, A_FEEDBACK_STATIC, A_FINAL_GRADE,
  A_GRADE_ANALYSIS, A_HIDE_FULL_ID, A_INJECTION_FLAG, A_INTEGRITY_FLAG, A_MISSING_ASSIGNMENT,
  A_NETWORK_ERROR, A_NO_DATA, A_OPEN, A_ORAL_DEFENSE, A_PROF_REPORT, A_QUESTION_N,
  A_REPLACEMENT, A_SHORT_ID, A_SHOW_FULL_ID, A_TIME_UP_BADGE, A_TIME_UP_TITLE, A_TIMED_OUT,
  A_TRANSCRIPT, A_UNDERSTANDING, AUTHORSHIP_LABELS, ID_NOTICES, t, tf,
} from "@/lib/adminStrings";

const STORAGE_KEY = "admin_auth";

/**
 * Grader-produced prose is stored in whatever language it was generated in (Hebrew today,
 * even for English exams), so it is always rendered dir="auto" rather than following the
 * admin UI direction.
 */
function MarkdownText({ text, className }: { text: string; className?: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <p className={`text-gray-300 text-sm leading-relaxed whitespace-pre-wrap ${className ?? ""}`} dir="auto">
      {parts.map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={i} className="text-white font-semibold">{part.slice(2, -2)}</strong>
        ) : (
          part
        )
      )}
    </p>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CodeReviewDisplay({ cr }: { cr: Record<string, any> }) {
  return (
    <div className="space-y-4 text-sm">
      {Object.entries(cr).map(([key, value]) => {
        const label = key.replace(/([A-Z])/g, " $1").replace(/_/g, " ").trim();
        if (value !== null && typeof value === "object" && !Array.isArray(value)) {
          return (
            <div key={key}>
              <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide font-medium">{label}</p>
              <div className="ps-3 border-s border-gray-700 space-y-2">
                {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                {Object.entries(value as Record<string, any>).map(([k, v]) => (
                  <div key={k}>
                    <span className="text-xs text-gray-500 uppercase tracking-wide">
                      {k.replace(/([A-Z])/g, " $1").replace(/_/g, " ").trim()}:{" "}
                    </span>
                    <span className="text-gray-200" dir="auto">
                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        }
        return (
          <div key={key}>
            <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide font-medium">{label}</p>
            <p className="text-gray-200 leading-relaxed" dir="auto">{String(value)}</p>
          </div>
        );
      })}
    </div>
  );
}

function Collapsible({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const { lang } = useAdminLang();
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900">
      <button
        className="w-full flex items-center justify-between px-5 py-4 text-start"
        onClick={() => setOpen(!open)}
      >
        <span className="font-semibold text-gray-200">{title}</span>
        <span className="text-gray-500 text-sm">{open ? t(A_CLOSE, lang) : t(A_OPEN, lang)}</span>
      </button>
      {open && <div className="px-5 pb-5 border-t border-gray-800 pt-4">{children}</div>}
    </div>
  );
}

function ScoreCard({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div className="rounded-lg bg-gray-800 px-5 py-4 text-center">
      <p className="text-sm text-gray-400 mb-1">{label}</p>
      <p className="text-3xl font-bold text-white">{value ?? "—"}</p>
    </div>
  );
}

function difficultyLabel(diff: string, lang: Language): string {
  return diff === "easy"   ? t(A_DIFF_EASY, lang)
       : diff === "medium" ? t(A_DIFF_MEDIUM, lang)
       :                     t(A_DIFF_HARD, lang);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function TranscriptSection({ transcript, timedOutAtQuestion }: { transcript: any[]; timedOutAtQuestion?: number | null }) {
  const { lang } = useAdminLang();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const examinerTurns = transcript.filter((t: any) => t?.role?.toLowerCase() === "examiner");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const studentTurns  = transcript.filter((t: any) => t?.role?.toLowerCase() === "student");

  // Filter by action instead of slice(0,-1) — slice breaks when session ends without FINISH_EXAM
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const examinerQuestionTurns = examinerTurns.filter((t: any) => {
    const action = t?.content?.action;
    return action !== "FINISH_EXAM" && action !== "END_EXAM_DISTRESS";
  });

  // Score for turn i is in the next examiner turn's internalEvaluation
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const perQScores = examinerQuestionTurns.map((turn: any) => {
    const fullIdx = examinerTurns.indexOf(turn);
    const next = examinerTurns[fullIdx + 1];
    const s = next?.content?.internalEvaluation?.understandingScore;
    return typeof s === "number" ? s : null;
  });

  const difficultyColors: Record<string, string> = {
    easy:   "bg-green-800 text-green-200",
    medium: "bg-yellow-800 text-yellow-200",
    hard:   "bg-red-800 text-red-200",
  };

  return (
    <div className="space-y-4">
      {examinerQuestionTurns.map((examTurn: any, i: number) => { // eslint-disable-line @typescript-eslint/no-explicit-any
        const q = examTurn?.content;
        const studentTurn = studentTurns[i];
        const studentAnswer = studentTurn?.content ?? "";
        const diff = (examTurn?.chosen_topic?.difficulty ?? q?.chosenTopicDifficulty ?? "").toLowerCase();
        const score = perQScores[i];
        const isSwitch = examTurn?.switch_replacement === true;
        const isReask = examTurn?.reask === true;
        const studentSwitched = studentTurn?.switch_event === true;
        const qNum = q?.questionNumber ?? (i + 1);
        const isTimedOutHere = timedOutAtQuestion != null && qNum === timedOutAtQuestion;

        return (
          <div key={i} className={`rounded-xl border bg-gray-900/50 p-4 space-y-3 ${isTimedOutHere ? "border-orange-800/70" : isSwitch ? "border-blue-800" : "border-gray-800"}`}>
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-indigo-300">
                  {tf(A_QUESTION_N, lang, { n: qNum })}{isSwitch ? t(A_REPLACEMENT, lang) : ""}
                </span>
                {isTimedOutHere && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-orange-900/50 text-orange-300" title={t(A_TIME_UP_TITLE, lang)}>{t(A_TIME_UP_BADGE, lang)}</span>
                )}
                {isReask && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300">RE_ASK</span>
                )}
                {diff && !isReask && (
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${difficultyColors[diff] ?? "bg-gray-700 text-gray-300"}`}>
                    {difficultyLabel(diff, lang)}
                  </span>
                )}
                {examTurn?.chosen_topic?.focus && (
                  <span className="text-xs text-gray-500 truncate max-w-xs" dir="auto">{examTurn.chosen_topic.focus}</span>
                )}
              </div>
              {score !== null && score !== undefined && (
                <span className="text-sm text-gray-400 tabular-nums">
                  {t(A_UNDERSTANDING, lang)} <span className="text-white font-medium">{score}/5</span>
                </span>
              )}
            </div>
            <p className="text-gray-200 text-sm leading-relaxed" dir="auto">{q?.questionText}</p>
            {studentAnswer && (
              <div className="border-t border-gray-800 pt-3">
                <p className="text-xs text-gray-500 mb-1">
                  {studentSwitched ? t(A_ANSWER_SWITCH, lang) : t(A_ANSWER, lang)}
                </p>
                <p className="text-gray-300 text-sm whitespace-pre-wrap leading-relaxed" dir="auto">{studentAnswer}</p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function StudentDetailContent() {
  const params = useParams<{ username: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { lang, dir } = useAdminLang();

  const username = params.username;
  const assignment = searchParams.get("assignment") ?? "";

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [revealFullId, setRevealFullId] = useState(false);

  useEffect(() => {
    const auth = sessionStorage.getItem(STORAGE_KEY);
    if (!auth) {
      router.replace("/admin");
      return;
    }
    if (!assignment) {
      setError(t(A_MISSING_ASSIGNMENT, lang));
      setLoading(false);
      return;
    }
    fetch(`/api/admin/results/by-github/${encodeURIComponent(username)}?assignment=${encodeURIComponent(assignment)}`, {
      headers: { "X-Admin-Key": auth },
    })
      .then(async (res) => {
        if (res.status === 401) { router.replace("/admin"); return; }
        const body = await res.json();
        if (!res.ok) { setError(body?.detail ?? body?.error ?? tf(A_ERROR_N, lang, { n: res.status })); return; }
        setData(body);
      })
      .catch(() => setError(t(A_NETWORK_ERROR, lang)))
      .finally(() => setLoading(false));
  }, [username, assignment, router, lang]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <span className="w-6 h-6 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin inline-block" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4" dir={dir}>
        <div className="text-center space-y-4">
          <p className="text-red-400">{error ?? t(A_NO_DATA, lang)}</p>
          <button onClick={() => router.back()} className="text-indigo-400 hover:text-indigo-300 text-sm">{t(A_BACK, lang)}</button>
        </div>
      </div>
    );
  }

  const fg = data.final_grade ?? {};
  const gv = data.grader_verdict ?? {};
  const cr = data.code_review ?? {};
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const transcript: any[] = Array.isArray(data.transcript) ? data.transcript : [];

  const idStatus = data.id_resolution_status as string;
  const idNotice = ID_NOTICES[idStatus];
  const idNoticeText = idNotice ? t(idNotice.text, lang) : "";
  const authorship = gv.authorshipAssessment as string;

  return (
    <div className="min-h-screen bg-gray-950 text-white py-10 px-4" dir={dir}>
      <div className="max-w-3xl mx-auto space-y-6">

        {/* Nav */}
        <div className="flex items-center justify-between gap-4">
          <button onClick={() => router.back()} className="text-sm text-gray-500 hover:text-gray-300 transition-colors">
            <span aria-hidden="true">← </span>{t(A_BACK, lang)}
          </button>
          <AdminLangToggle />
        </div>

        {/* Header */}
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-3">
          <div className="flex items-start justify-between flex-wrap gap-2">
            <div>
              <h1 className="text-xl font-bold text-white" dir="auto">{data.hebrew_name ?? data.github_username}</h1>
              <p className="text-gray-400 text-sm mt-0.5">
                <code className="bg-gray-800 px-1.5 py-0.5 rounded text-indigo-300">{data.github_username}</code>
                {" · "}
                {data.assignment_name}
                {data.timed_out && (
                  <span className="ms-2 text-xs bg-orange-900/40 text-orange-300 px-2 py-0.5 rounded-full">{t(A_TIMED_OUT, lang)}</span>
                )}
              </p>
            </div>
            {authorship && (
              <span className={`text-xs px-3 py-1 rounded-full font-medium ${
                authorship === "established" ? "bg-green-900/40 text-green-300" :
                authorship === "partial"     ? "bg-yellow-900/40 text-yellow-300" :
                                              "bg-red-900/40 text-red-300"
              }`}>
                {AUTHORSHIP_LABELS[authorship] ? t(AUTHORSHIP_LABELS[authorship], lang) : authorship}
              </span>
            )}
          </div>

          {/* ID info */}
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="text-gray-500">{t(A_SHORT_ID, lang)}</span>
            <span className="text-gray-200 font-mono">{data.student_id ?? "—"}</span>
            <button
              onClick={() => setRevealFullId(!revealFullId)}
              className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              {revealFullId ? t(A_HIDE_FULL_ID, lang) : t(A_SHOW_FULL_ID, lang)}
            </button>
            {revealFullId && (
              <span className="text-gray-200 font-mono">{data.full_id ?? data.full_id_from_repo ?? "—"}</span>
            )}
          </div>

          {idNoticeText && (
            <span className={`inline-block text-xs px-3 py-1 rounded-full ${idNotice.color}`}>
              {idNoticeText}
              {data.id_resolution_detail && ` — ${data.id_resolution_detail}`}
            </span>
          )}

          {(gv.integrityFlag || gv.promptInjectionFlag) && (
            <div className="flex flex-wrap gap-2">
              {gv.integrityFlag && (
                <span className="text-xs px-3 py-1 rounded-full bg-red-900/40 text-red-300">{t(A_INTEGRITY_FLAG, lang)}</span>
              )}
              {gv.promptInjectionFlag && (
                <span className="text-xs px-3 py-1 rounded-full bg-red-900/40 text-red-300">{t(A_INJECTION_FLAG, lang)}</span>
              )}
            </div>
          )}

          {/* Email status */}
          <div className="flex flex-wrap items-center gap-2">
            <span className={`text-xs px-3 py-1 rounded-full ${
              data.grade_email_sent ? "bg-green-900/40 text-green-300" : "bg-gray-700 text-gray-400"
            }`}>
              {data.grade_email_sent ? t(A_EMAIL_SENT, lang) : t(A_EMAIL_NOT_SENT, lang)}
            </span>
            {data.email_validation && !data.email_validation.is_valid && (
              <span className="text-xs px-3 py-1 rounded-full bg-red-900/40 text-red-300">
                {tf(A_EMAIL_MISSING, lang, { fields: (data.email_validation.missing_fields as string[]).join(", ") })}
              </span>
            )}
          </div>
        </div>

        {/* Scores */}
        <div className="grid grid-cols-3 gap-4">
          <ScoreCard label={t(A_ORAL_DEFENSE, lang)} value={fg.oralDefenseScore} />
          <ScoreCard label={t(A_CODE_QUALITY, lang)} value={fg.staticCodeQualityScore} />
          <ScoreCard label={t(A_FINAL_GRADE, lang)} value={fg.finalWeightedGrade} />
        </div>

        {/* Professor report */}
        {data.professor_report && (
          <Collapsible title={t(A_PROF_REPORT, lang)} defaultOpen>
            <MarkdownText text={data.professor_report} />
          </Collapsible>
        )}

        {/* Student feedback — oral */}
        {gv.studentFeedback && (
          <Collapsible title={t(A_FEEDBACK_ORAL, lang)}>
            <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap" dir="auto">
              {gv.studentFeedback}
            </p>
          </Collapsible>
        )}

        {/* Student feedback — static code */}
        {cr.studentStaticFeedback && (
          <Collapsible title={t(A_FEEDBACK_STATIC, lang)}>
            <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap" dir="auto">
              {cr.studentStaticFeedback}
            </p>
          </Collapsible>
        )}

        {/* Transcript */}
        {transcript.length > 0 && (
          <Collapsible title={t(A_TRANSCRIPT, lang)} defaultOpen>
            <TranscriptSection
              transcript={transcript}
              timedOutAtQuestion={data.timed_out ? (data.timeout_metadata?.timed_out_at_question ?? null) : null}
            />
          </Collapsible>
        )}

        {/* Grader scratchpad */}
        {gv.grading_scratchpad && (
          <Collapsible title={t(A_GRADE_ANALYSIS, lang)}>
            <div className="space-y-3 text-sm text-gray-300">
              {Object.entries(gv.grading_scratchpad as Record<string, string>).map(([k, v]) => (
                <div key={k}>
                  <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide">{k.replace(/_/g, " ")}</p>
                  <p className="leading-relaxed" dir="auto">{v || "—"}</p>
                </div>
              ))}
            </div>
          </Collapsible>
        )}

        {/* Academic dishonesty */}
        {gv.academicDishonestyReasoning && (
          <Collapsible title={t(A_AUTHORSHIP_NOTE, lang)}>
            <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap" dir="auto">
              {gv.academicDishonestyReasoning}
            </p>
          </Collapsible>
        )}

        {/* Code review */}
        {Object.keys(cr).length > 0 && (
          <Collapsible title={t(A_CODE_REVIEW, lang)}>
            <CodeReviewDisplay cr={cr} />
          </Collapsible>
        )}

        {/* Email preview */}
        {data.email_preview && !data.email_preview.error && (
          <Collapsible title={t(A_EMAIL_PREVIEW, lang)}>
            <div className="space-y-3">
              <p className="text-xs text-gray-500">
                {t(A_EMAIL_SUBJECT, lang)} <span className="text-gray-300" dir="auto">{data.email_preview.subject}</span>
              </p>
              <pre className="text-gray-300 text-xs leading-relaxed whitespace-pre-wrap font-sans bg-gray-800/50 rounded-lg p-4 max-h-96 overflow-y-auto" dir="auto">
                {data.email_preview.body}
              </pre>
            </div>
          </Collapsible>
        )}

      </div>
    </div>
  );
}

export default function StudentDetailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-950" />}>
      <StudentDetailContent />
    </Suspense>
  );
}
