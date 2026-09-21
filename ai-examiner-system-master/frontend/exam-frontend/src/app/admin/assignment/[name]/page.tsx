"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useParams, useRouter } from "next/navigation";
import { Suspense } from "react";
import { AdminLangToggle, useAdminLang } from "@/lib/adminLang";
import {
  A_ALL_STUDENTS, A_AUTH_DIST, A_AVERAGES, A_BACK, A_BADGE_FLAG, A_BADGE_ID, A_BADGE_SWITCH,
  A_BADGE_TIMEOUT, A_CANCEL, A_CLOSE_BTN, A_COL_AUTHORSHIP, A_COL_CODE, A_COL_DURATION,
  A_COL_EMAIL_READY, A_COL_EMAIL_SENT, A_COL_FINAL, A_COL_ID, A_COL_NAME, A_COL_ORAL,
  A_COL_WHEN, A_DISCRIM_TITLE, A_DURATION_TITLE, A_ERROR_DETAIL, A_ERROR_N, A_EXPORT_CSV,
  A_EXPORTING, A_FILTER_BAD_ID, A_FILTER_CLEAR, A_FILTER_EMPTY, A_FILTER_FLAGGED,
  A_FILTER_MAX, A_FILTER_SWITCH, A_FILTER_TIMEOUT, A_FLAGGED, A_GRADE_DIST, A_ICOL_CEILING,
  A_ICOL_DISCRIM, A_ICOL_DIVERGENCE, A_ICOL_RECS, A_ICOL_RESIDUAL, A_ICOL_TAKE,
  A_ID_STATUS_TITLE, A_ITEM_COMPUTED, A_ITEM_DEF_CEILING, A_ITEM_DEF_DISCRIM,
  A_ITEM_DEF_DIVERGENCE, A_ITEM_DEF_NOTE, A_ITEM_DEF_RESIDUAL, A_ITEM_DEF_TAKE,
  A_ITEM_LEGEND_TITLE,
  A_ITEM_NO_DIV, A_ITEM_NO_QS, A_ITEM_NO_REPORT, A_ITEM_OK, A_ITEM_PENDING, A_ITEM_TITLE,
  A_MEDIAN, A_N_EXAMINED, A_N_EXAMS, A_N_INCOMPLETE, A_NETWORK_ERROR, A_NO_DATA, A_NONE,
  A_OVERVIEW_TITLE, A_PART_LOADING, A_PARTICIPATION, A_QCOL_ASKED, A_QCOL_AVG,
  A_QCOL_DIFFICULTY, A_QCOL_ID, A_QCOL_REASKED, A_QCOL_SWITCHED, A_QCOL_TOPIC,
  A_QSTATS_EMPTY, A_QSTATS_TITLE, A_REFRESH, A_REFRESH_TITLE, A_REM_ALL_DONE, A_REM_BODY,
  A_REM_BODY_HINT, A_REM_CAL_LINK, A_REM_CAL_WARN, A_REM_NO_EMAIL, A_REM_PENDING,
  A_REM_RESULT, A_REM_SELECT_ALL, A_REM_SEND_N, A_REM_SENT, A_REM_SUBJECT, A_REM_TEST,
  A_REM_TEST_OK, A_REM_TITLE, A_SEND_REMINDERS, A_SENDING, A_STAT_AVG_AI, A_STAT_AVG_AI_T,
  A_STAT_AVG_EXAM, A_STAT_AVG_EXAM_T, A_STAT_EMAILED, A_STAT_EXAMINED, A_STAT_NO_ROSTER,
  A_STAT_POST_SURVEY, A_STAT_PRE_SURVEY, A_UPDATED_AT, AUTHORSHIP_LABELS, ID_STATUS_LABELS,
  t, tf,
} from "@/lib/adminStrings";

const STORAGE_KEY = "admin_auth";

interface StudentSummary {
  github_username: string;
  student_id: string | null;
  hebrew_name: string | null;
  final_grade: number | null;
  oral_score: number | null;
  code_score: number | null;
  authorship_assessment: string | null;
  integrity_flag: boolean | null;
  prompt_injection_flag: boolean | null;
  id_resolution_status: string | null;
  timed_out: boolean | null;
  switch_used: boolean | null;
  exam_start_time: string | null;
  session_minutes: number | null;
}

const BAD_ID_STATUSES = new Set([
  "name_not_in_roster", "ambiguous_5_digit_match", "missing_file",
  "empty_file", "no_digits", "wrong_length", "fetch_error",
]);

function StudentBadges({ s }: { s: StudentSummary }) {
  const { lang } = useAdminLang();
  return (
    <span className="flex flex-wrap gap-1 mt-0.5">
      {s.timed_out && (
        <span className="text-xs px-1.5 py-0 rounded-full bg-orange-900/50 text-orange-300" title={t(A_BADGE_TIMEOUT, lang)}>⏱</span>
      )}
      {s.switch_used && (
        <span className="text-xs px-1.5 py-0 rounded-full bg-blue-900/50 text-blue-300" title={t(A_BADGE_SWITCH, lang)}>↔</span>
      )}
      {s.id_resolution_status && BAD_ID_STATUSES.has(s.id_resolution_status) && (
        <span className="text-xs px-1.5 py-0 rounded-full bg-yellow-900/50 text-yellow-300" title={tf(A_BADGE_ID, lang, { status: s.id_resolution_status })}>⚠</span>
      )}
      {(s.integrity_flag || s.prompt_injection_flag) && (
        <span className="text-xs px-1.5 py-0 rounded-full bg-red-900/50 text-red-300" title={t(A_BADGE_FLAG, lang)}>🚩</span>
      )}
    </span>
  );
}

interface StatsStudent {
  github_username: string;
  hebrew_name: string | null;
  full_id: string | null;
  grade_email_sent: boolean | null;
  email_valid: boolean;
  missing_fields: string[];
  on_calendar: boolean | null;
  filled_pre_survey: boolean | null;
  filled_post_survey: boolean | null;
}

interface CalendarCrossRef {
  ghost_slots:      { email: string; slot_time: string; invalidated?: boolean }[];
  wrong_time_slots: { email: string; slot_time: string; exam_time: string; github_username?: string; hebrew_name?: string | null }[];
  mismatches:       { expected_email: string; expected_username: string; actual_username: string; actual_hebrew_name: string | null; actual_email: string | null; slot_time: string; session_start_time: string }[];
  no_slot:          { github_username: string; hebrew_name: string | null; exam_start_time: string }[];
}

interface AssignmentStats {
  assignment: string;
  graded_count: number;
  email_sent_count: number;
  required_ids: string[] | null;
  required_ids_error: string | null;
  calendar_count: number | null;
  calendar_by_day: Record<string, number> | null;
  calendar_by_hour: Record<string, Record<string, number>> | null;
  calendar_error: string | null;
  calendar_cross_ref: CalendarCrossRef | null;
  pre_survey_count: number | null;
  pre_survey_row_count: number | null;
  pre_survey_error: string | null;
  post_survey_count: number | null;
  post_survey_error: string | null;
  avg_session_minutes: number | null;
  avg_ai_response_seconds: number | null;
  students: StatsStudent[];
}

interface QuestionStat {
  id: string;
  focus: string;
  files: string[];
  difficulty: string;
  dimension: string;
  times_asked: number;
  times_switched: number;
  times_reasked: number;
  times_scored: number;
  avg_score: number | null;
}

interface QuestionStatsData {
  assignment: string;
  session_count: number;
  questions: QuestionStat[];
}

// ── Item-analysis report (nightly job → GCS → /api/admin/results/item-analysis) ──
interface ItemAnalysisQuestion {
  qid: string;
  difficulty: string;
  dimension: string | null;
  asked: number;
  take_rate: number | null;
  n_scored: number;
  mean_score: number | null;
  residual: number | null;
  discrimination: number | null;
  pct_ceiling_5: number | null;
  divergence: number | null;
  divergence_band: "green" | "yellow" | "red" | "gray";
  recommendations: string[];
}

interface ItemAnalysisData {
  assignment: string;
  computed: boolean;
  computed_at?: string;
  divergence_available?: boolean;
  global_mean_score?: number;
  questions?: ItemAnalysisQuestion[];
  hint?: string;
}

interface ReminderStudent {
  full_id: string;
  email: string;
  name: string;
}

interface ReminderPreview {
  students: ReminderStudent[];
  registered_count: number;
  total_required: number;
  no_email_count: number;
  default_subject: string;
  default_body: string;
  calendar_error: string | null;
}

function ReminderModal({
  assignmentName,
  onClose,
}: {
  assignmentName: string;
  onClose: () => void;
}) {
  const { lang, dir } = useAdminLang();
  const [step, setStep] = useState<"loading" | "preview" | "sending" | "done" | "error">("loading");
  const [preview, setPreview] = useState<ReminderPreview | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [subject, setSubject] = useState("");
  const [bodyTemplate, setBodyTemplate] = useState("");
  const [calendarLink, setCalendarLink] = useState("");
  const [sendResult, setSendResult] = useState<{ sent: number; failed: number; errors: string[] } | null>(null);
  const [testSending, setTestSending] = useState(false);
  // ok/text kept separate so the colour doesn't depend on matching translated text.
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    const auth = sessionStorage.getItem("admin_auth") ?? "";
    fetch(`/api/admin/assignment/${encodeURIComponent(assignmentName)}/reminder-preview`, {
      headers: { "X-Admin-Key": auth },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        return res.json() as Promise<ReminderPreview>;
      })
      .then((data) => {
        setPreview(data);
        setSubject(data.default_subject);
        setBodyTemplate(data.default_body);
        setSelected(new Set(data.students.map((s) => s.full_id)));
        setStep("preview");
      })
      .catch((e) => {
        setErrorMsg(String(e));
        setStep("error");
      });
  }, [assignmentName]);

  async function handleSend() {
    if (!preview) return;
    const auth = sessionStorage.getItem("admin_auth") ?? "";
    const students = preview.students.filter((s) => selected.has(s.full_id));
    setStep("sending");
    try {
      const res = await fetch(
        `/api/admin/assignment/${encodeURIComponent(assignmentName)}/send-reminder-emails`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Admin-Key": auth },
          body: JSON.stringify({ students, subject, body_template: bodyTemplate, calendar_link: calendarLink }),
        },
      );
      const data = await res.json();
      setSendResult(data);
      setStep("done");
    } catch (e) {
      setErrorMsg(String(e));
      setStep("error");
    }
  }

  async function handleTestSend() {
    const auth = sessionStorage.getItem("admin_auth") ?? "";
    setTestSending(true);
    setTestResult(null);
    try {
      const res = await fetch(`/api/admin/send-test-reminder-email`, {
        method: "POST",
        headers: { "X-Admin-Key": auth },
      });
      const data = await res.json();
      setTestResult(
        res.ok
          ? { ok: true,  text: tf(A_REM_TEST_OK, lang, { to: data.from ?? "" }) }
          : { ok: false, text: tf(A_ERROR_DETAIL, lang, { detail: data.detail ?? data.error ?? "unknown" }) },
      );
    } catch (e) {
      setTestResult({ ok: false, text: tf(A_ERROR_DETAIL, lang, { detail: String(e) }) });
    } finally {
      setTestSending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4" dir={dir}>
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h2 className="text-lg font-semibold text-white">{t(A_REM_TITLE, lang)}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-xl leading-none">×</button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {step === "loading" && (
            <div className="flex justify-center py-8">
              <span className="w-6 h-6 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
            </div>
          )}

          {step === "error" && (
            <p className="text-red-400 text-sm">{errorMsg}</p>
          )}

          {step === "done" && sendResult && (
            <div className="space-y-2">
              <p className="text-green-400 font-medium">{t(A_REM_SENT, lang)}</p>
              <p className="text-gray-300 text-sm">
                {tf(A_REM_RESULT, lang, { sent: sendResult.sent, failed: sendResult.failed })}
              </p>
              {sendResult.errors.length > 0 && (
                <ul className="text-xs text-red-400 space-y-1 mt-2">
                  {sendResult.errors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              )}
            </div>
          )}

          {(step === "preview" || step === "sending") && preview && (
            <>
              {preview.calendar_error && (
                <p className="text-xs text-yellow-400">
                  {tf(A_REM_CAL_WARN, lang, { error: preview.calendar_error })}
                </p>
              )}
              <p className="text-sm text-gray-400">
                {tf(A_REM_PENDING, lang, { n: preview.students.length, total: preview.total_required })}
                {preview.no_email_count > 0 && tf(A_REM_NO_EMAIL, lang, { n: preview.no_email_count })}
              </p>

              {/* Student checklist */}
              {preview.students.length > 0 ? (
                <div className="border border-gray-700 rounded-lg overflow-hidden">
                  <div className="flex items-center gap-2 px-3 py-2 bg-gray-800/50 border-b border-gray-700">
                    <input
                      type="checkbox"
                      checked={selected.size === preview.students.length}
                      onChange={(e) =>
                        setSelected(e.target.checked ? new Set(preview.students.map((s) => s.full_id)) : new Set())
                      }
                      className="accent-indigo-500"
                    />
                    <span className="text-xs text-gray-400">{t(A_REM_SELECT_ALL, lang)}</span>
                  </div>
                  <div className="max-h-48 overflow-y-auto">
                    {preview.students.map((s) => (
                      <label key={s.full_id} className="flex items-center gap-3 px-3 py-2 hover:bg-gray-800/30 cursor-pointer border-b border-gray-800/50 last:border-0">
                        <input
                          type="checkbox"
                          checked={selected.has(s.full_id)}
                          onChange={(e) => {
                            const next = new Set(selected);
                            if (e.target.checked) next.add(s.full_id);
                            else next.delete(s.full_id);
                            setSelected(next);
                          }}
                          className="accent-indigo-500 shrink-0"
                        />
                        <span className="text-sm text-gray-200 flex-1" dir="auto">{s.name || s.full_id}</span>
                        <span className="text-xs text-gray-500 font-mono" dir="ltr">{s.email}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-green-400">{t(A_REM_ALL_DONE, lang)}</p>
              )}

              {/* Calendar link */}
              <div>
                <label className="text-xs text-gray-400 block mb-1">{t(A_REM_CAL_LINK, lang)}</label>
                <input
                  type="text"
                  value={calendarLink}
                  onChange={(e) => setCalendarLink(e.target.value)}
                  placeholder="https://calendar.google.com/..."
                  dir="ltr"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Subject */}
              <div>
                <label className="text-xs text-gray-400 block mb-1">{t(A_REM_SUBJECT, lang)}</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  dir="auto"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Body */}
              <div>
                <label className="text-xs text-gray-400 block mb-1">
                  {t(A_REM_BODY, lang)}{" "}
                  <span className="text-gray-600">{t(A_REM_BODY_HINT, lang)}</span>
                </label>
                <textarea
                  value={bodyTemplate}
                  onChange={(e) => setBodyTemplate(e.target.value)}
                  rows={8}
                  dir="auto"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white font-mono focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-y"
                />
              </div>
            </>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-800 flex flex-col gap-2">
          {testResult && (
            <p className={`text-xs text-center ${testResult.ok ? "text-green-400" : "text-red-400"}`}>
              {testResult.text}
            </p>
          )}
          <div className="flex justify-between items-center">
            <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-300">
              {step === "done" ? t(A_CLOSE_BTN, lang) : t(A_CANCEL, lang)}
            </button>
            <div className="flex gap-2 items-center">
              {step === "preview" && (
                <button
                  onClick={handleTestSend}
                  disabled={testSending}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-gray-300 rounded-lg text-sm transition-colors"
                >
                  {testSending ? t(A_SENDING, lang) : t(A_REM_TEST, lang)}
                </button>
              )}
              {(step === "preview" || step === "sending") && (
                <button
                  onClick={handleSend}
                  disabled={step === "sending" || selected.size === 0}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  {step === "sending" ? t(A_SENDING, lang) : tf(A_REM_SEND_N, lang, { n: selected.size })}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface AggregateData {
  assignment: string;
  count: number;
  stats?: {
    oral_defense?: { mean: number; median: number; min: number; max: number } | null;
    code_quality?: { mean: number; median: number; min: number; max: number } | null;
    final_grade?: { mean: number; median: number; min: number; max: number } | null;
  };
  histogram?: { labels: string[]; values: number[] };
  authorship?: Record<string, number>;
  id_resolution?: Record<string, number>;
  timed_out_count?: number;
  flagged?: StudentSummary[];
  outliers?: StudentSummary[];
  all_students?: StudentSummary[];
}

function computeStdDev(values: (number | null)[]): number | null {
  const nums = values.filter((v): v is number => v !== null);
  if (nums.length < 2) return null;
  const mean = nums.reduce((a, b) => a + b, 0) / nums.length;
  const variance = nums.reduce((sum, v) => sum + (v - mean) ** 2, 0) / nums.length;
  return Math.round(Math.sqrt(variance) * 10) / 10;
}

function StatCard({ label, stats, sd }: {
  label: string;
  stats?: { mean: number; median: number; min: number; max: number } | null;
  sd?: number | null;
}) {
  const { lang } = useAdminLang();
  if (!stats) return (
    <div className="rounded-lg bg-gray-800 px-4 py-3 text-center">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-lg font-bold text-gray-600">—</p>
    </div>
  );
  return (
    <div className="rounded-lg bg-gray-800 px-4 py-3 text-center">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">{stats.mean}</p>
      <p className="text-xs text-gray-500 mt-0.5" dir="ltr">
        {tf(A_MEDIAN, lang, { v: stats.median })} · {stats.min}–{stats.max}
      </p>
      {sd != null && <p className="text-xs text-gray-600 mt-0.5">σ = {sd}</p>}
    </div>
  );
}

function Histogram({ labels, values }: { labels: string[]; values: number[] }) {
  const max = Math.max(...values, 1);
  const totalHeight = 80;
  const barWidth = 28;
  const gap = 4;
  const totalWidth = labels.length * (barWidth + gap) - gap;

  return (
    <div dir="ltr">
      <svg
        width={totalWidth}
        height={totalHeight + 24}
        className="overflow-visible"
        aria-label="histogram"
        role="img"
      >
        {values.map((v, i) => {
          const barH = Math.round((v / max) * totalHeight);
          const x = i * (barWidth + gap);
          const y = totalHeight - barH;
          const isHighEnd = i >= 8;
          return (
            <g key={i}>
              <rect
                x={x} y={y} width={barWidth} height={barH}
                className={isHighEnd ? "fill-indigo-500" : "fill-gray-600"}
                rx={2}
              />
              <text
                x={x + barWidth / 2} y={totalHeight + 14}
                textAnchor="middle"
                fontSize={9}
                className="fill-gray-500"
              >
                {labels[i]}
              </text>
              {v > 0 && (
                <text
                  x={x + barWidth / 2} y={y - 3}
                  textAnchor="middle"
                  fontSize={9}
                  className="fill-gray-400"
                >
                  {v}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function formatExamTime(iso: string | null, locale: string): string {
  if (!iso) return "—";
  // Backend stores UTC via datetime.utcnow() without "Z"; append it so JS parses as UTC.
  const utcStr = /[Z+]/.test(iso.slice(10)) ? iso : iso + "Z";
  const d = new Date(utcStr);
  return d.toLocaleString(locale, {
    timeZone: "Asia/Jerusalem",
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

type NumSortCol = "final_grade" | "oral_score" | "code_score";
type SortCol    = NumSortCol | "exam_start_time";

function StudentTable({
  students,
  assignment,
  sortable = false,
}: {
  students: StudentSummary[];
  assignment: string;
  sortable?: boolean;
}) {
  const { lang, locale } = useAdminLang();
  const [sortBy, setSortBy] = useState<SortCol | null>("exam_start_time");
  const [sortAsc, setSortAsc] = useState(false);
  const router = useRouter();

  if (!students.length) return <p className="text-gray-500 text-sm">{t(A_NONE, lang)}</p>;

  function onSortClick(col: SortCol) {
    if (sortBy === col) setSortAsc((p) => !p);
    else { setSortBy(col); setSortAsc(false); }
  }

  const displayed = sortBy
    ? [...students].sort((a, b) => {
        if (sortBy === "exam_start_time") {
          const av = a.exam_start_time ?? "";
          const bv = b.exam_start_time ?? "";
          const cmp = av < bv ? -1 : av > bv ? 1 : 0;
          return sortAsc ? cmp : -cmp;
        }
        const av = a[sortBy as NumSortCol] ?? -1;
        const bv = b[sortBy as NumSortCol] ?? -1;
        return sortAsc ? av - bv : bv - av;
      })
    : students;

  function ColTh({ col, children }: { col: SortCol; children: ReactNode }) {
    if (!sortable) return <th className="pb-2 font-medium ps-3">{children}</th>;
    const active = sortBy === col;
    return (
      <th
        className={`pb-2 font-medium ps-3 cursor-pointer select-none transition-colors hover:text-gray-300 ${active ? "text-indigo-400" : ""}`}
        onClick={() => onSortClick(col)}
      >
        {children}{active ? (sortAsc ? " ↑" : " ↓") : " ↕"}
      </th>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-start">
        <thead>
          <tr className="text-gray-500 border-b border-gray-800">
            <th className="pb-2 font-medium ps-3">{t(A_COL_NAME, lang)}</th>
            <th className="pb-2 font-medium ps-3">{t(A_COL_ID, lang)}</th>
            <ColTh col="final_grade">{t(A_COL_FINAL, lang)}</ColTh>
            <ColTh col="oral_score">{t(A_COL_ORAL, lang)}</ColTh>
            <ColTh col="code_score">{t(A_COL_CODE, lang)}</ColTh>
            <ColTh col="exam_start_time">{t(A_COL_WHEN, lang)}</ColTh>
            <th className="pb-2 font-medium ps-3 text-center" title={t(A_DURATION_TITLE, lang)}>{t(A_COL_DURATION, lang)}</th>
            <th className="pb-2 font-medium">{t(A_COL_AUTHORSHIP, lang)}</th>
          </tr>
        </thead>
        <tbody>
          {displayed.map((s) => (
            <tr
              key={s.github_username}
              className="border-b border-gray-800/50 hover:bg-gray-800/30 cursor-pointer transition-colors"
              onClick={() => router.push(`/admin/student/${encodeURIComponent(s.github_username)}?assignment=${encodeURIComponent(assignment)}`)}
            >
              <td className="py-2 ps-3">
                <p className="text-gray-200" dir="auto">{s.hebrew_name ?? s.github_username}</p>
                <p className="text-xs text-gray-500" dir="ltr">{s.github_username}</p>
                <StudentBadges s={s} />
              </td>
              <td className="py-2 ps-3 text-gray-400 font-mono text-xs">{s.student_id ?? "—"}</td>
              <td className="py-2 ps-3 font-semibold text-white">{s.final_grade ?? "—"}</td>
              <td className="py-2 ps-3 text-gray-300">{s.oral_score ?? "—"}</td>
              <td className="py-2 ps-3 text-gray-300">{s.code_score ?? "—"}</td>
              <td className="py-2 ps-3 text-gray-400 text-xs">{formatExamTime(s.exam_start_time, locale)}</td>
              <td className="py-2 ps-3 text-center text-gray-300 tabular-nums text-xs">
                {s.session_minutes != null ? `${s.session_minutes}′` : <span className="text-gray-600">—</span>}
              </td>
              <td className="py-2">
                {s.authorship_assessment && (
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    s.authorship_assessment === "established" ? "bg-green-900/40 text-green-300" :
                    s.authorship_assessment === "partial"     ? "bg-yellow-900/40 text-yellow-300" :
                                                               "bg-red-900/40 text-red-300"
                  }`}>
                    {AUTHORSHIP_LABELS[s.authorship_assessment]
                      ? t(AUTHORSHIP_LABELS[s.authorship_assessment], lang)
                      : s.authorship_assessment}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AssignmentOverviewContent() {
  const params = useParams<{ name: string }>();
  const router = useRouter();
  const { lang, dir, locale } = useAdminLang();
  const assignmentName = decodeURIComponent(params.name);

  const [data, setData] = useState<AggregateData | null>(null);
  const [stats, setStats] = useState<AssignmentStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [questionStats, setQuestionStats] = useState<QuestionStatsData | null>(null);
  const [itemAnalysis, setItemAnalysis] = useState<ItemAnalysisData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showReminder, setShowReminder] = useState(false);
  const [filterTimedOut, setFilterTimedOut]   = useState(false);
  const [filterSwitched, setFilterSwitched]   = useState(false);
  const [filterBadId,    setFilterBadId]      = useState(false);
  const [filterFlagged,  setFilterFlagged]    = useState(false);
  const [filterMaxGrade, setFilterMaxGrade]   = useState("");

  const fetchData = useCallback((force = false) => {
    const auth = sessionStorage.getItem(STORAGE_KEY);
    if (!auth) { router.replace("/admin"); return; }

    const forceParam = force ? "&force=true" : "";
    const enc = encodeURIComponent(assignmentName);
    setRefreshing(true);
    // Fast, Postgres-backed dashboard: grades from result_summary, plus question-stats and the
    // item-analysis report. The slow calendar stats are fetched separately (see fetchStats).
    Promise.all([
      fetch(`/api/admin/results/aggregate_fast?assignment=${enc}${forceParam}`,   { headers: { "X-Admin-Key": auth } }),
      fetch(`/api/admin/assignment/${enc}/question-stats?_=1${forceParam}`,      { headers: { "X-Admin-Key": auth } }),
      fetch(`/api/admin/results/item-analysis?assignment=${enc}`,                { headers: { "X-Admin-Key": auth } }),
    ])
      .then(async ([aggRes, qsRes, iaRes]) => {
        if (aggRes.status === 401) { router.replace("/admin"); return; }
        const aggBody = await aggRes.json();
        if (!aggRes.ok) { setError(aggBody?.detail ?? aggBody?.error ?? tf(A_ERROR_N, lang, { n: aggRes.status })); return; }
        setData(aggBody);
        if (qsRes.ok)     setQuestionStats(await qsRes.json());
        if (iaRes.ok)     setItemAnalysis(await iaRes.json());
        setLastUpdated(new Date());
      })
      .catch(() => setError(t(A_NETWORK_ERROR, lang)))
      .finally(() => { setLoading(false); setRefreshing(false); });
  }, [assignmentName, router, lang]);

  // Calendar/participation stats hit the Google Calendar API and can be slow or time out.
  // Fetch them on their own so a slow/504 call never blocks the main dashboard; the section
  // (at the bottom) simply appears when ready and stays hidden on failure.
  const fetchStats = useCallback(() => {
    const auth = sessionStorage.getItem(STORAGE_KEY);
    if (!auth) return;
    setStatsLoading(true);
    fetch(`/api/admin/stats/${encodeURIComponent(assignmentName)}?_=1`, { headers: { "X-Admin-Key": auth } })
      .then(async (res) => { if (res.ok) setStats(await res.json()); })
      .catch(() => { /* non-fatal — participation section stays hidden */ })
      .finally(() => setStatsLoading(false));
  }, [assignmentName]);

  useEffect(() => { fetchData(); fetchStats(); }, [fetchData, fetchStats]);

  async function handleExport() {
    const auth = sessionStorage.getItem(STORAGE_KEY);
    if (!auth) return;
    setExporting(true);
    try {
      const res = await fetch(`/api/admin/results/export?assignment=${encodeURIComponent(assignmentName)}`, {
        headers: { "X-Admin-Key": auth },
      });
      if (!res.ok) { alert("Export failed"); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${assignmentName}_results.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Export failed");
    } finally {
      setExporting(false);
    }
  }

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

  const _all = data.all_students ?? [];
  const oralSd  = computeStdDev(_all.map((s) => s.oral_score));
  const codeSd  = computeStdDev(_all.map((s) => s.code_score));
  const finalSd = computeStdDev(_all.map((s) => s.final_grade));

  return (
    <div className="min-h-screen bg-gray-950 text-white py-10 px-4" dir={dir}>
      <div className="max-w-4xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <button onClick={() => router.back()} className="text-sm text-gray-500 hover:text-gray-300 transition-colors mb-3 block">
              <span aria-hidden="true">← </span>{t(A_BACK, lang)}
            </button>
            <h1 className="text-2xl font-bold text-white">{tf(A_OVERVIEW_TITLE, lang, { name: assignmentName })}</h1>
            <div className="flex items-center gap-3 mt-1">
              <p className="text-gray-400">{tf(A_N_EXAMINED, lang, { n: data.count })}</p>
              {lastUpdated && (
                <span className="text-xs text-gray-600">
                  {tf(A_UPDATED_AT, lang, {
                    time: lastUpdated.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" }),
                  })}
                </span>
              )}
              <button
                onClick={() => { fetchData(true); fetchStats(); }}
                disabled={refreshing}
                className="text-xs text-indigo-400 hover:text-indigo-300 disabled:opacity-40 transition-colors flex items-center gap-1"
                title={t(A_REFRESH_TITLE, lang)}
              >
                {refreshing
                  ? <span className="w-3 h-3 rounded-full border border-indigo-400 border-t-transparent animate-spin inline-block" />
                  : t(A_REFRESH, lang)}
              </button>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <AdminLangToggle />
            <button
              onClick={handleExport}
              disabled={exporting || data.count === 0}
              className="px-5 py-2.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-white rounded-lg font-medium transition-colors"
            >
              {exporting ? t(A_EXPORTING, lang) : t(A_EXPORT_CSV, lang)}
            </button>
          </div>
        </div>

        {/* Score stats */}
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-200">{t(A_AVERAGES, lang)}</h2>
          <div className="grid grid-cols-3 gap-4">
            <StatCard label={t(A_COL_ORAL, lang)}  stats={data.stats?.oral_defense} sd={oralSd} />
            <StatCard label={t(A_COL_CODE, lang)}  stats={data.stats?.code_quality} sd={codeSd} />
            <StatCard label={t(A_COL_FINAL, lang)} stats={data.stats?.final_grade}  sd={finalSd} />
          </div>
          {data.timed_out_count ? (
            <p className="text-xs text-orange-400">{tf(A_N_INCOMPLETE, lang, { n: data.timed_out_count })}</p>
          ) : null}
        </section>

        {/* Histogram */}
        {data.histogram && (
          <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
            <h2 className="text-lg font-semibold text-gray-200">{t(A_GRADE_DIST, lang)}</h2>
            <div className="overflow-x-auto">
              <Histogram labels={data.histogram.labels} values={data.histogram.values} />
            </div>
          </section>
        )}

        {/* Authorship distribution */}
        {data.authorship && Object.keys(data.authorship).length > 0 && (
          <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-3">
            <h2 className="text-lg font-semibold text-gray-200">{t(A_AUTH_DIST, lang)}</h2>
            <div className="flex flex-wrap gap-3">
              {Object.entries(data.authorship).map(([k, v]) => (
                <div key={k} className={`rounded-lg px-4 py-3 text-center min-w-[100px] ${
                  k === "established"     ? "bg-green-900/30 border border-green-800/50" :
                  k === "partial"         ? "bg-yellow-900/30 border border-yellow-800/50" :
                  k === "not_established" ? "bg-red-900/30 border border-red-800/50" :
                                            "bg-gray-800 border border-gray-700"
                }`}>
                  <p className="text-2xl font-bold text-white">{v}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {AUTHORSHIP_LABELS[k] ? t(AUTHORSHIP_LABELS[k], lang) : k}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ID resolution breakdown */}
        {data.id_resolution && Object.keys(data.id_resolution).length > 0 && (
          <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-3">
            <h2 className="text-lg font-semibold text-gray-200">{t(A_ID_STATUS_TITLE, lang)}</h2>
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.id_resolution)
                .sort(([, a], [, b]) => b - a)
                .map(([k, v]) => (
                  <span key={k} className="text-sm bg-gray-800 px-3 py-1 rounded-full text-gray-300">
                    {ID_STATUS_LABELS[k] ? t(ID_STATUS_LABELS[k], lang) : k}: <span className="text-white font-medium">{v}</span>
                  </span>
                ))}
            </div>
          </section>
        )}

        {/* Flagged students */}
        {(data.flagged?.length ?? 0) > 0 && (
          <section className="rounded-xl border border-red-900/50 bg-gray-900 p-6 space-y-4">
            <h2 className="text-lg font-semibold text-red-300">
              {tf(A_FLAGGED, lang, { n: data.flagged!.length })}
            </h2>
            <StudentTable students={data.flagged!} assignment={assignmentName} />
          </section>
        )}

        {/* All students */}
        {(data.all_students?.length ?? 0) > 0 && (() => {
          const maxGradeNum = filterMaxGrade !== "" ? parseInt(filterMaxGrade, 10) : null;
          const filtered = (data.all_students ?? []).filter((s) => {
            if (filterTimedOut && !s.timed_out) return false;
            if (filterSwitched && !s.switch_used) return false;
            if (filterBadId && (!s.id_resolution_status || !BAD_ID_STATUSES.has(s.id_resolution_status))) return false;
            if (filterFlagged && !s.integrity_flag && !s.prompt_injection_flag) return false;
            if (maxGradeNum !== null && !isNaN(maxGradeNum) && (s.final_grade ?? 101) > maxGradeNum) return false;
            return true;
          });

          const chip = (label: string, active: boolean, toggle: () => void) => (
            <button
              key={label}
              onClick={toggle}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                active
                  ? "bg-indigo-700 border-indigo-600 text-white"
                  : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              {label}
            </button>
          );

          return (
            <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
              <h2 className="text-lg font-semibold text-gray-200">
                {t(A_ALL_STUDENTS, lang)}
                <span className="text-sm font-normal text-gray-500 ms-2">
                  {filtered.length !== data.all_students!.length
                    ? `${filtered.length} / ${data.all_students!.length}`
                    : data.all_students!.length}
                </span>
              </h2>

              {/* Filter bar */}
              <div className="flex flex-wrap items-center gap-2">
                {chip(t(A_FILTER_TIMEOUT, lang), filterTimedOut, () => setFilterTimedOut(!filterTimedOut))}
                {chip(t(A_FILTER_SWITCH, lang),  filterSwitched, () => setFilterSwitched(!filterSwitched))}
                {chip(t(A_FILTER_BAD_ID, lang),  filterBadId,    () => setFilterBadId(!filterBadId))}
                {chip(t(A_FILTER_FLAGGED, lang), filterFlagged,  () => setFilterFlagged(!filterFlagged))}
                <div className="flex items-center gap-1.5 text-xs text-gray-400">
                  <span>{t(A_FILTER_MAX, lang)}</span>
                  <input
                    type="number"
                    min={0} max={100}
                    value={filterMaxGrade}
                    onChange={(e) => setFilterMaxGrade(e.target.value)}
                    placeholder="—"
                    className="w-14 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-white text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
                {(filterTimedOut || filterSwitched || filterBadId || filterFlagged || filterMaxGrade !== "") && (
                  <button
                    onClick={() => { setFilterTimedOut(false); setFilterSwitched(false); setFilterBadId(false); setFilterFlagged(false); setFilterMaxGrade(""); }}
                    className="text-xs text-gray-500 hover:text-gray-300 underline"
                  >
                    {t(A_FILTER_CLEAR, lang)}
                  </button>
                )}
              </div>

              {filtered.length > 0
                ? <StudentTable students={filtered} assignment={assignmentName} sortable />
                : <p className="text-sm text-gray-500">{t(A_FILTER_EMPTY, lang)}</p>
              }
            </section>
          );
        })()}

        {/* Question statistics */}
        {questionStats && (
          <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
            <div className="flex items-baseline gap-3">
              <h2 className="text-lg font-semibold text-gray-200">{t(A_QSTATS_TITLE, lang)}</h2>
              <span className="text-sm text-gray-500">{tf(A_N_EXAMS, lang, { n: questionStats.session_count })}</span>
            </div>
            {questionStats.questions.length === 0 ? (
              <p className="text-sm text-gray-500">{t(A_QSTATS_EMPTY, lang)}</p>
            ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-start">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-800">
                    <th className="pb-2 font-medium ps-3">{t(A_QCOL_ID, lang)}</th>
                    <th className="pb-2 font-medium ps-3">{t(A_QCOL_TOPIC, lang)}</th>
                    <th className="pb-2 font-medium ps-3">{t(A_QCOL_DIFFICULTY, lang)}</th>
                    <th className="pb-2 font-medium ps-3 text-center">{t(A_QCOL_ASKED, lang)}</th>
                    <th className="pb-2 font-medium ps-3 text-center">{t(A_QCOL_SWITCHED, lang)}</th>
                    <th className="pb-2 font-medium ps-3 text-center">{t(A_QCOL_REASKED, lang)}</th>
                    <th className="pb-2 font-medium text-center">{t(A_QCOL_AVG, lang)}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...questionStats.questions]
                    .sort((a, b) => {
                      if (a.avg_score === null && b.avg_score === null) return 0;
                      if (a.avg_score === null) return 1;
                      if (b.avg_score === null) return -1;
                      return b.avg_score - a.avg_score;
                    })
                    .map((q) => {
                    const scoreColor =
                      q.avg_score === null ? "text-gray-600" :
                      q.avg_score >= 4.0   ? "text-green-400" :
                      q.avg_score >= 2.5   ? "text-yellow-400" :
                                             "text-red-400";
                    const switchRate = q.times_asked > 0
                      ? Math.round((q.times_switched / q.times_asked) * 100)
                      : 0;
                    return (
                      <tr key={q.id} className="border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors">
                        <td className="py-2 ps-3 font-mono text-xs text-gray-400">{q.id}</td>
                        <td className="py-2 ps-3 text-gray-200 max-w-[220px]">
                          <p className="truncate" title={q.focus} dir="auto">{q.focus}</p>
                          <p className="text-xs text-gray-600 truncate" title={q.files?.[0]} dir="ltr">{q.files?.[0]}</p>
                        </td>
                        <td className="py-2 ps-3">
                          {q.difficulty && (
                            <span className={`text-xs px-2 py-0.5 rounded-full ${
                              q.difficulty === "easy"   ? "bg-green-900/40 text-green-300" :
                              q.difficulty === "hard"   ? "bg-red-900/40 text-red-300" :
                                                          "bg-gray-800 text-gray-400"
                            }`}>{q.difficulty}</span>
                          )}
                        </td>
                        <td className="py-2 ps-3 text-center text-gray-200">{q.times_asked}</td>
                        <td className="py-2 ps-3 text-center">
                          <span className={q.times_switched > 0 ? "text-orange-400" : "text-gray-600"}>
                            {q.times_switched}
                          </span>
                          {q.times_asked > 0 && q.times_switched > 0 && (
                            <span className="text-xs text-gray-600 ms-1">({switchRate}%)</span>
                          )}
                        </td>
                        <td className="py-2 ps-3 text-center">
                          <span className={q.times_reasked > 0 ? "text-blue-400" : "text-gray-600"}>
                            {q.times_reasked}
                          </span>
                        </td>
                        <td className="py-2 text-center">
                          <span className={`font-semibold ${scoreColor}`}>
                            {q.avg_score !== null ? q.avg_score.toFixed(2) : "—"}
                          </span>
                          {q.times_scored > 0 && (
                            <span className="text-xs text-gray-600 ms-1">({q.times_scored})</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            )}
          </section>
        )}

        {/* Question-pool item analysis (nightly job) */}
        {itemAnalysis && (
          <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
            <div className="flex items-baseline gap-3 flex-wrap">
              <h2 className="text-lg font-semibold text-gray-200">{t(A_ITEM_TITLE, lang)}</h2>
              {itemAnalysis.computed ? (
                <span className="text-sm text-gray-500">
                  {tf(A_ITEM_COMPUTED, lang, {
                    time: itemAnalysis.computed_at
                      ? new Date(itemAnalysis.computed_at).toLocaleString(locale, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
                      : "",
                  })}
                  {itemAnalysis.divergence_available === false && t(A_ITEM_NO_DIV, lang)}
                </span>
              ) : (
                <span className="text-sm text-yellow-500">{t(A_ITEM_PENDING, lang)}</span>
              )}
            </div>
            {!itemAnalysis.computed ? (
              <p className="text-sm text-gray-500">{itemAnalysis.hint ?? t(A_ITEM_NO_REPORT, lang)}</p>
            ) : (itemAnalysis.questions?.length ?? 0) === 0 ? (
              <p className="text-sm text-gray-500">{t(A_ITEM_NO_QS, lang)}</p>
            ) : (
              <>
                <details className="rounded-lg border border-gray-800 bg-gray-800/30">
                  <summary className="cursor-pointer px-4 py-2 text-xs font-medium text-gray-400 hover:text-gray-200">
                    {t(A_ITEM_LEGEND_TITLE, lang)}
                  </summary>
                  <dl className="grid gap-3 px-4 pb-4 pt-1 text-xs leading-relaxed text-gray-500">
                    {([
                      [t(A_ICOL_TAKE, lang),       t(A_ITEM_DEF_TAKE, lang)],
                      [t(A_ICOL_RESIDUAL, lang),   t(A_ITEM_DEF_RESIDUAL, lang)],
                      [t(A_ICOL_CEILING, lang),    t(A_ITEM_DEF_CEILING, lang)],
                      [t(A_ICOL_DISCRIM, lang),    t(A_ITEM_DEF_DISCRIM, lang)],
                      [t(A_ICOL_DIVERGENCE, lang), t(A_ITEM_DEF_DIVERGENCE, lang)],
                    ] as [string, string][]).map(([term, def]) => (
                      <div key={term} className="grid grid-cols-[max-content_1fr] gap-x-3">
                        <dt className="font-medium text-gray-300 whitespace-nowrap">{term}</dt>
                        <dd className="m-0">{def}</dd>
                      </div>
                    ))}
                    <p className="m-0 border-t border-gray-800 pt-3 text-gray-600">
                      {t(A_ITEM_DEF_NOTE, lang)}
                    </p>
                  </dl>
                </details>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-start">
                    <thead>
                      <tr className="text-gray-500 border-b border-gray-800">
                        <th className="pb-2 font-medium ps-3">{t(A_QCOL_ID, lang)}</th>
                        <th className="pb-2 font-medium ps-3">{t(A_QCOL_DIFFICULTY, lang)}</th>
                        <th className="pb-2 font-medium ps-3 text-center">{t(A_QCOL_ASKED, lang)}</th>
                        <th className="pb-2 font-medium ps-3 text-center">{t(A_ICOL_TAKE, lang)}</th>
                        <th className="pb-2 font-medium ps-3 text-center">{t(A_ICOL_RESIDUAL, lang)}</th>
                        <th className="pb-2 font-medium ps-3 text-center">{t(A_ICOL_CEILING, lang)}</th>
                        <th className="pb-2 font-medium ps-3 text-center">{t(A_ICOL_DISCRIM, lang)}</th>
                        <th className="pb-2 font-medium ps-3 text-center">{t(A_ICOL_DIVERGENCE, lang)}</th>
                        <th className="pb-2 font-medium">{t(A_ICOL_RECS, lang)}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...(itemAnalysis.questions ?? [])]
                        .sort((a, b) => (b.divergence ?? -1) - (a.divergence ?? -1))
                        .map((q) => {
                          const bandDot =
                            q.divergence_band === "green"  ? "🟢" :
                            q.divergence_band === "yellow" ? "🟡" :
                            q.divergence_band === "red"    ? "🔴" : "⚪";
                          return (
                            <tr key={q.qid} className="border-b border-gray-800/50 hover:bg-gray-800/20 transition-colors align-top">
                              <td className="py-2 ps-3 font-mono text-xs text-gray-400">{q.qid}</td>
                              <td className="py-2 ps-3">
                                <span className={`text-xs px-2 py-0.5 rounded-full ${
                                  q.difficulty === "easy" ? "bg-green-900/40 text-green-300" :
                                  q.difficulty === "hard" ? "bg-red-900/40 text-red-300" :
                                                            "bg-gray-800 text-gray-400"
                                }`}>{q.difficulty}</span>
                              </td>
                              <td className="py-2 ps-3 text-center text-gray-200">{q.asked}</td>
                              <td className="py-2 ps-3 text-center text-gray-400">
                                {q.take_rate !== null ? `${Math.round(q.take_rate * 100)}%` : "—"}
                              </td>
                              <td className="py-2 ps-3 text-center text-gray-400">
                                {q.residual !== null ? (q.residual > 0 ? `+${q.residual.toFixed(2)}` : q.residual.toFixed(2)) : "—"}
                              </td>
                              <td className="py-2 ps-3 text-center text-gray-400">
                                {q.pct_ceiling_5 !== null ? `${q.pct_ceiling_5}%` : "—"}
                              </td>
                              <td className="py-2 ps-3 text-center whitespace-nowrap"
                                  title={t(A_DISCRIM_TITLE, lang)}>
                                {q.discrimination !== null ? (
                                  <span className={
                                    q.discrimination >= 0.15  ? "text-green-400" :
                                    q.discrimination <= -0.15 ? "text-orange-400" :
                                                                "text-gray-500"
                                  }>
                                    {q.discrimination > 0 ? `+${q.discrimination.toFixed(2)}` : q.discrimination.toFixed(2)}
                                  </span>
                                ) : <span className="text-gray-600">—</span>}
                              </td>
                              <td className="py-2 ps-3 text-center whitespace-nowrap">
                                {bandDot} <span className="text-xs text-gray-500">{q.divergence !== null ? q.divergence.toFixed(2) : ""}</span>
                              </td>
                              <td className="py-2 text-xs text-gray-400 max-w-[320px]">
                                {q.recommendations.length === 0
                                  ? <span className="text-gray-600">{t(A_ITEM_OK, lang)}</span>
                                  : q.recommendations.map((r, i) => <p key={i} className="mb-0.5" dir="auto">{r}</p>)}
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
        )}

        {/* Reminder modal */}
        {showReminder && (
          <ReminderModal assignmentName={assignmentName} onClose={() => setShowReminder(false)} />
        )}

        {/* Participation & email status — loaded separately (slow calendar); stays at the bottom */}
        {statsLoading && !stats && (
          <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 flex items-center gap-3 text-sm text-gray-500">
            <span className="w-3 h-3 rounded-full border border-gray-500 border-t-transparent animate-spin inline-block" />
            {t(A_PART_LOADING, lang)}
          </section>
        )}
        {stats && (
          <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-200">{t(A_PARTICIPATION, lang)}</h2>
              {stats.required_ids && (
                <button
                  onClick={() => setShowReminder(true)}
                  className="px-4 py-1.5 bg-indigo-700 hover:bg-indigo-600 text-white text-sm rounded-lg font-medium transition-colors"
                >
                  {t(A_SEND_REMINDERS, lang)}
                </button>
              )}
            </div>

            {/* Summary counters */}
            <div className="flex flex-wrap gap-3">
              <div className="rounded-lg bg-gray-800 px-4 py-3 text-center min-w-[90px]">
                <p className="text-2xl font-bold text-white">
                  {stats.graded_count}
                  {stats.required_ids && (
                    <span className="text-base text-gray-400">/{stats.required_ids.length}</span>
                  )}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">{t(A_STAT_EXAMINED, lang)}</p>
                {stats.required_ids_error && (
                  <p className="text-xs text-red-400 mt-0.5" title={stats.required_ids_error}>{t(A_STAT_NO_ROSTER, lang)}</p>
                )}
              </div>
              <div className="rounded-lg bg-gray-800 px-4 py-3 text-center min-w-[90px]">
                <p className="text-2xl font-bold text-white">{stats.email_sent_count}</p>
                <p className="text-xs text-gray-400 mt-0.5">{t(A_STAT_EMAILED, lang)}</p>
              </div>
              <div className={`rounded-lg px-4 py-3 text-center min-w-[90px] ${stats.pre_survey_error ? "bg-gray-800/50" : "bg-gray-800"}`}
                   title={stats.pre_survey_error ?? undefined}>
                <p className="text-2xl font-bold text-white">{stats.pre_survey_count ?? "—"}</p>
                <p className="text-xs text-gray-400 mt-0.5">{t(A_STAT_PRE_SURVEY, lang)}</p>
                {stats.pre_survey_error && (
                  <p className="text-xs text-red-400 mt-0.5 max-w-[120px] truncate"
                     title={stats.pre_survey_error}>{t(A_NETWORK_ERROR, lang)}</p>
                )}
              </div>
              <div className={`rounded-lg px-4 py-3 text-center min-w-[90px] ${stats.post_survey_error ? "bg-gray-800/50" : "bg-gray-800"}`}
                   title={stats.post_survey_error ?? undefined}>
                <p className="text-2xl font-bold text-white">{stats.post_survey_count ?? "—"}</p>
                <p className="text-xs text-gray-400 mt-0.5">{t(A_STAT_POST_SURVEY, lang)}</p>
                {stats.post_survey_error && (
                  <p className="text-xs text-red-400 mt-0.5 max-w-[120px] truncate"
                     title={stats.post_survey_error}>{t(A_NETWORK_ERROR, lang)}</p>
                )}
              </div>
              {stats.avg_session_minutes !== null && stats.avg_session_minutes !== undefined && (
                <div className="rounded-lg bg-gray-800 px-4 py-3 text-center min-w-[90px]"
                     title={t(A_STAT_AVG_EXAM_T, lang)}>
                  <p className="text-2xl font-bold text-white">{stats.avg_session_minutes}<span className="text-base text-gray-400">′</span></p>
                  <p className="text-xs text-gray-400 mt-0.5">{t(A_STAT_AVG_EXAM, lang)}</p>
                </div>
              )}
              {stats.avg_ai_response_seconds !== null && stats.avg_ai_response_seconds !== undefined && (
                <div className="rounded-lg bg-gray-800 px-4 py-3 text-center min-w-[90px]"
                     title={t(A_STAT_AVG_AI_T, lang)}>
                  <p className="text-2xl font-bold text-white">{stats.avg_ai_response_seconds}<span className="text-base text-gray-400">″</span></p>
                  <p className="text-xs text-gray-400 mt-0.5">{t(A_STAT_AVG_AI, lang)}</p>
                </div>
              )}
            </div>

            {/* Per-student participation table */}
            {stats.students.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-start">
                  <thead>
                    <tr className="text-gray-500 border-b border-gray-800">
                      <th className="pb-2 font-medium ps-3">{t(A_COL_NAME, lang)}</th>
                      <th className="pb-2 font-medium ps-3 text-center">{t(A_STAT_PRE_SURVEY, lang)}</th>
                      <th className="pb-2 font-medium ps-3 text-center">{t(A_STAT_POST_SURVEY, lang)}</th>
                      <th className="pb-2 font-medium ps-3 text-center">{t(A_COL_EMAIL_SENT, lang)}</th>
                      <th className="pb-2 font-medium text-center">{t(A_COL_EMAIL_READY, lang)}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.students.map((s) => (
                      <tr
                        key={s.github_username}
                        className="border-b border-gray-800/50 hover:bg-gray-800/30 cursor-pointer transition-colors"
                        onClick={() => router.push(`/admin/student/${encodeURIComponent(s.github_username)}?assignment=${encodeURIComponent(assignmentName)}`)}
                      >
                        <td className="py-2 ps-3">
                          <p className="text-gray-200" dir="auto">{s.hebrew_name ?? s.github_username}</p>
                          <p className="text-xs text-gray-500" dir="ltr">{s.github_username}</p>
                        </td>
                        {[s.filled_pre_survey, s.filled_post_survey, s.grade_email_sent].map((val, i) => (
                          <td key={i} className="py-2 ps-3 text-center">
                            {val === null || val === undefined
                              ? <span className="text-gray-600">—</span>
                              : val
                                ? <span className="text-green-400">✓</span>
                                : <span className="text-red-400">✗</span>
                            }
                          </td>
                        ))}
                        <td className="py-2 text-center">
                          {s.email_valid
                            ? <span className="text-green-400">✓</span>
                            : <span className="text-xs text-red-400" title={s.missing_fields.join(", ")}>✗</span>
                          }
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

          </section>
        )}

      </div>
    </div>
  );
}

export default function AssignmentOverviewPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-950" />}>
      <AssignmentOverviewContent />
    </Suspense>
  );
}
