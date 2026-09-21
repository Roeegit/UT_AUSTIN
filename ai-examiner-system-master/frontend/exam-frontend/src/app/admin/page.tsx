"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AdminLangToggle, useAdminLang } from "@/lib/adminLang";
import {
  A_ASSIGN_OVERVIEW, A_BAD_PASSWORD, A_CURRENT_STATUS, A_ENABLE_RETAKE, A_ENABLING,
  A_ERROR_DETAIL, A_FIND_STUDENT, A_STUDENT_IDENTIFIER, A_HOME_TITLE, A_INVALIDATE_BTN,
  A_INVALIDATE_TITLE, A_INVALIDATED_OK, A_INVALIDATING, A_LOADING_ASSIGN, A_LOADING_SESSIONS,
  A_LOGIN_SUB, A_LOGIN_TITLE, A_LOGIN_UNAVAIL, A_NET_RETRY, A_NETWORK_ERROR_D, A_NO_ASSIGNMENTS,
  A_NO_SESSIONS, A_OVERVIEW_BTN, A_PASSWORD, A_PICK_ASSIGNMENT, A_RETAKE_OK, A_SIGN_IN, A_SIGN_OUT,
  A_SIGNING_IN, A_VIEW_STUDENT, t, tf,
} from "@/lib/adminStrings";

const STORAGE_KEY = "admin_auth";

function AssignmentSelect({
  assignments,
  loading,
  value,
  onChange,
  placeholder,
}: {
  assignments: string[];
  loading: boolean;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  const { lang } = useAdminLang();
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={loading}
      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 appearance-none disabled:opacity-50"
    >
      <option value="" disabled>
        {loading
          ? t(A_LOADING_ASSIGN, lang)
          : assignments.length === 0
            ? t(A_NO_ASSIGNMENTS, lang)
            : placeholder}
      </option>
      {assignments.map((a) => (
        <option key={a} value={a}>{a}</option>
      ))}
    </select>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const { lang, dir } = useAdminLang();
  const [isAuthed, setIsAuthed] = useState(false);
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);

  // Shared assignment state (both sections share the same dropdown value)
  const [searchUsername, setSearchUsername] = useState("");
  const [searchAssignment, setSearchAssignment] = useState("");

  // All assignments (for overview section, loaded on auth)
  const [allAssignments, setAllAssignments] = useState<string[]>([]);
  const [allLoading, setAllLoading] = useState(false);

  // Student-specific assignments (loaded when username is committed)
  const [studentAssignments, setStudentAssignments] = useState<string[]>([]);
  const [studentAssignmentsLoading, setStudentAssignmentsLoading] = useState(false);
  const lastFetchedUsername = useRef("");

  // Invalidate session tool
  const [invalidateUsername, setInvalidateUsername] = useState("");
  const [invalidateSessions, setInvalidateSessions] = useState<
    { assignment_name: string; status: string; session_id: string }[]
  >([]);
  const [invalidateSessionsLoading, setInvalidateSessionsLoading] = useState(false);
  const [selectedSession, setSelectedSession] = useState<{ assignment_name: string; session_id: string } | null>(null);
  // Keep ok/text separate rather than sniffing the message text — the message is translated.
  const [invalidateResult, setInvalidateResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [invalidateLoading, setInvalidateLoading] = useState<string | null>(null);
  const lastInvalidateFetched = useRef("");

  useEffect(() => {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      setIsAuthed(true);
      fetchAllAssignments(stored);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function fetchAllAssignments(auth: string) {
    setAllLoading(true);
    try {
      const res = await fetch("/api/admin/results/assignments", {
        headers: { "X-Admin-Key": auth },
      });
      if (res.ok) {
        const data = await res.json();
        setAllAssignments(data.assignments ?? []);
        if (data.assignments?.length === 1) setSearchAssignment(data.assignments[0]);
      }
    } finally {
      setAllLoading(false);
    }
  }

  async function fetchStudentAssignments(username: string) {
    const auth = sessionStorage.getItem(STORAGE_KEY) ?? "";
    if (!username.trim() || username === lastFetchedUsername.current) return;
    lastFetchedUsername.current = username;
    setStudentAssignmentsLoading(true);
    setStudentAssignments([]);
    try {
      const res = await fetch(
        `/api/admin/results/assignments?github_username=${encodeURIComponent(username)}`,
        { headers: { "X-Admin-Key": auth } },
      );
      if (res.ok) {
        const data = await res.json();
        const list: string[] = data.assignments ?? [];
        setStudentAssignments(list);
        // Auto-select if only one option
        if (list.length === 1) setSearchAssignment(list[0]);
      }
    } finally {
      setStudentAssignmentsLoading(false);
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoginLoading(true);
    setLoginError("");
    try {
      const res = await fetch("/api/admin/results/assignments", {
        headers: { "X-Admin-Key": password },
      });
      if (res.status === 401) {
        setLoginError(t(A_BAD_PASSWORD, lang));
        return;
      }
      // Any other non-OK status means the password was never actually verified —
      // e.g. the backend is unreachable and the proxy returns 500. Signing in here
      // would grant access on an unchecked password, so fail closed instead.
      if (!res.ok) {
        setLoginError(tf(A_LOGIN_UNAVAIL, lang, { n: res.status }));
        return;
      }
      sessionStorage.setItem(STORAGE_KEY, password);
      setIsAuthed(true);
      const data = await res.json();
      setAllAssignments(data.assignments ?? []);
      if (data.assignments?.length === 1) setSearchAssignment(data.assignments[0]);
    } catch {
      setLoginError(t(A_NET_RETRY, lang));
    } finally {
      setLoginLoading(false);
    }
  }

  function handleSignOut() {
    sessionStorage.removeItem(STORAGE_KEY);
    setIsAuthed(false);
    setPassword("");
    setAllAssignments([]);
    setStudentAssignments([]);
    lastFetchedUsername.current = "";
  }

  function goToStudent(e: React.FormEvent) {
    e.preventDefault();
    if (!searchUsername.trim() || !searchAssignment.trim()) return;
    router.push(
      `/admin/student/${encodeURIComponent(searchUsername.trim())}?assignment=${encodeURIComponent(searchAssignment.trim())}`,
    );
  }

  function goToAssignment(e: React.FormEvent) {
    e.preventDefault();
    if (!searchAssignment.trim()) return;
    router.push(`/admin/assignment/${encodeURIComponent(searchAssignment.trim())}`);
  }

  async function fetchInvalidateSessions(username: string) {
    const auth = sessionStorage.getItem(STORAGE_KEY) ?? "";
    if (!username.trim() || username === lastInvalidateFetched.current) return;
    lastInvalidateFetched.current = username;
    setInvalidateSessions([]);
    setSelectedSession(null);
    setInvalidateResult(null);
    setInvalidateSessionsLoading(true);
    try {
      const res = await fetch(`/api/admin/student-sessions/${encodeURIComponent(username)}`, {
        headers: { "X-Admin-Key": auth },
      });
      if (res.ok) {
        const data = await res.json();
        setInvalidateSessions(data);
        if (data.length === 1) setSelectedSession({ assignment_name: data[0].assignment_name, session_id: data[0].session_id });
      }
    } finally {
      setInvalidateSessionsLoading(false);
    }
  }

  async function handleInvalidate(newStatus: "invalidated" | "retake_enabled") {
    if (!selectedSession) return;
    const auth = sessionStorage.getItem(STORAGE_KEY) ?? "";
    setInvalidateLoading(newStatus);
    setInvalidateResult(null);
    try {
      const res = await fetch("/api/admin/invalidate-session", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Key": auth },
        body: JSON.stringify({
          github_username:  invalidateUsername.trim(),
          assignment_name:  selectedSession.assignment_name,
          reason:           "admin invalidation via UI",
          new_status:       newStatus,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        const n = data.invalidated_sessions?.length ?? 0;
        setInvalidateResult({
          ok: true,
          text: tf(newStatus === "invalidated" ? A_INVALIDATED_OK : A_RETAKE_OK, lang, { n }),
        });
        setInvalidateSessions((prev) =>
          prev.map((s) =>
            s.assignment_name === selectedSession.assignment_name
              ? { ...s, status: newStatus }
              : s,
          ),
        );
      } else {
        setInvalidateResult({
          ok: false,
          text: tf(A_ERROR_DETAIL, lang, { detail: data.detail ?? JSON.stringify(data) }),
        });
      }
    } catch (e) {
      setInvalidateResult({ ok: false, text: tf(A_NETWORK_ERROR_D, lang, { detail: String(e) }) });
    } finally {
      setInvalidateLoading(null);
    }
  }

  // The dropdown options for the student section:
  // prefer student-specific list when available, else fall back to all assignments
  const studentDropdownOptions =
    searchUsername.trim() && studentAssignments.length > 0
      ? studentAssignments
      : allAssignments;

  if (!isAuthed) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4" dir={dir}>
        <div className="w-full max-w-sm space-y-6">
          <div className="flex justify-center">
            <AdminLangToggle />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold text-white">{t(A_LOGIN_TITLE, lang)}</h1>
            <p className="text-gray-400 mt-1 text-sm">{t(A_LOGIN_SUB, lang)}</p>
          </div>
          <form onSubmit={handleLogin} className="space-y-4">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t(A_PASSWORD, lang)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              autoFocus
            />
            {loginError && <p className="text-red-400 text-sm text-center">{loginError}</p>}
            <button
              type="submit"
              disabled={loginLoading || !password}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-medium transition-colors"
            >
              {loginLoading ? t(A_SIGNING_IN, lang) : t(A_SIGN_IN, lang)}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white py-10 px-4" dir={dir}>
      <div className="max-w-2xl mx-auto space-y-8">
        <div className="flex items-center justify-between gap-4">
          <h1 className="text-2xl font-bold">{t(A_HOME_TITLE, lang)}</h1>
          <div className="flex items-center gap-3">
            <AdminLangToggle />
            <button
              onClick={handleSignOut}
              className="text-sm text-gray-500 hover:text-gray-300 transition-colors"
            >
              {t(A_SIGN_OUT, lang)}
            </button>
          </div>
        </div>

        {/* Student search */}
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-200">{t(A_FIND_STUDENT, lang)}</h2>
          <form onSubmit={goToStudent} className="space-y-3">
            <input
              type="text"
              value={searchUsername}
              onChange={(e) => {
                setSearchUsername(e.target.value);
                // Reset student-specific list when username changes
                if (e.target.value !== lastFetchedUsername.current) {
                  setStudentAssignments([]);
                }
              }}
              onBlur={(e) => fetchStudentAssignments(e.target.value)}
              placeholder={t(A_STUDENT_IDENTIFIER, lang)}
              dir="ltr"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-start"
            />
            <AssignmentSelect
              assignments={studentDropdownOptions}
              loading={studentAssignmentsLoading}
              value={searchAssignment}
              onChange={setSearchAssignment}
              placeholder={t(A_PICK_ASSIGNMENT, lang)}
            />
            <button
              type="submit"
              disabled={!searchUsername.trim() || !searchAssignment.trim()}
              className="w-full py-2.5 bg-indigo-700 hover:bg-indigo-600 disabled:opacity-40 text-white rounded-lg font-medium transition-colors"
            >
              {t(A_VIEW_STUDENT, lang)}
            </button>
          </form>
        </section>

        {/* Assignment overview */}
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-200">{t(A_ASSIGN_OVERVIEW, lang)}</h2>
          <form onSubmit={goToAssignment} className="flex gap-3 items-start">
            <div className="flex-1">
              <AssignmentSelect
                assignments={allAssignments}
                loading={allLoading}
                value={searchAssignment}
                onChange={setSearchAssignment}
                placeholder={t(A_PICK_ASSIGNMENT, lang)}
              />
            </div>
            <button
              type="submit"
              disabled={!searchAssignment.trim()}
              className="px-5 py-2.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-white rounded-lg font-medium transition-colors whitespace-nowrap"
            >
              {t(A_OVERVIEW_BTN, lang)}
            </button>
          </form>
        </section>

        {/* Invalidate session */}
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-200">{t(A_INVALIDATE_TITLE, lang)}</h2>
          <input
            type="text"
            value={invalidateUsername}
            onChange={(e) => {
              setInvalidateUsername(e.target.value);
              if (e.target.value !== lastInvalidateFetched.current) {
                setInvalidateSessions([]);
                setSelectedSession(null);
                setInvalidateResult(null);
              }
            }}
            onBlur={(e) => fetchInvalidateSessions(e.target.value)}
            placeholder={t(A_STUDENT_IDENTIFIER, lang)}
            dir="ltr"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-start"
          />

          {invalidateSessionsLoading && (
            <p className="text-sm text-gray-500">{t(A_LOADING_SESSIONS, lang)}</p>
          )}

          {invalidateSessions.length > 0 && (
            <div className="space-y-3">
              <select
                value={selectedSession?.assignment_name ?? ""}
                onChange={(e) => {
                  const s = invalidateSessions.find((x) => x.assignment_name === e.target.value);
                  setSelectedSession(s ? { assignment_name: s.assignment_name, session_id: s.session_id } : null);
                  setInvalidateResult(null);
                }}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 appearance-none"
              >
                <option value="" disabled>{t(A_PICK_ASSIGNMENT, lang)}</option>
                {invalidateSessions.map((s) => (
                  <option key={s.assignment_name} value={s.assignment_name}>
                    {s.assignment_name} — {s.status}
                  </option>
                ))}
              </select>

              {selectedSession && (() => {
                const s = invalidateSessions.find((x) => x.assignment_name === selectedSession.assignment_name);
                return s ? (
                  <p className="text-sm text-gray-400">
                    {t(A_CURRENT_STATUS, lang)}{" "}
                    <span className={
                      s.status === "graded"         ? "text-green-400" :
                      s.status === "invalidated"    ? "text-gray-500"  :
                      s.status === "retake_enabled" ? "text-amber-400" :
                      s.status === "complaint"      ? "text-yellow-400" :
                                                      "text-blue-400"
                    }>
                      {s.status}
                    </span>
                  </p>
                ) : null;
              })()}

              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => handleInvalidate("invalidated")}
                  disabled={!selectedSession || invalidateLoading !== null}
                  className="py-2.5 bg-red-800 hover:bg-red-700 disabled:opacity-40 text-white rounded-lg font-medium transition-colors"
                >
                  {invalidateLoading === "invalidated" ? t(A_INVALIDATING, lang) : t(A_INVALIDATE_BTN, lang)}
                </button>
                <button
                  onClick={() => handleInvalidate("retake_enabled")}
                  disabled={!selectedSession || invalidateLoading !== null}
                  className="py-2.5 bg-amber-700 hover:bg-amber-600 disabled:opacity-40 text-white rounded-lg font-medium transition-colors"
                >
                  {invalidateLoading === "retake_enabled" ? t(A_ENABLING, lang) : t(A_ENABLE_RETAKE, lang)}
                </button>
              </div>
            </div>
          )}

          {invalidateSessions.length === 0 && !invalidateSessionsLoading && invalidateUsername && lastInvalidateFetched.current === invalidateUsername && (
            <p className="text-sm text-gray-500">{t(A_NO_SESSIONS, lang)}</p>
          )}

          {invalidateResult && (
            <p className={`text-sm font-medium ${invalidateResult.ok ? "text-green-400" : "text-red-400"}`}>
              {invalidateResult.text}
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
