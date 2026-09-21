"use client";

import { useEffect, useState } from "react";
import CodeViewer from "./CodeViewer";
import MarkdownViewer from "./MarkdownViewer";
import {
  ID_CONFIRM_LABEL,
  ID_NO_FILES,
  ID_WRONG_IDENTIFIER,
  SUB_CONFIRM_BTN,
  SUB_CONFIRM_SUBTITLE,
  SUB_CONFIRM_TITLE,
  SUB_LOAD_ERROR,
  SUB_NETWORK_ERROR,
  SUB_PROBLEM_NOTE,
  ti,
  ts,
  type IdentityMode,
  type SubmissionKind,
} from "@/lib/courseStrings";

interface RosterConfirmScreenProps {
  githubUsername: string;
  assignmentName: string;
  onConfirm: (githubUsername: string) => void;
  onBack: () => void;
  identityMode: IdentityMode;
  submissionKind: SubmissionKind;
}

type Mode = "confirm" | "complaint" | "complaint_contact" | "complaint_sending" | "complaint_done" | "complaint_error";

export default function RosterConfirmScreen({
  githubUsername: initialGithub,
  assignmentName,
  onConfirm,
  onBack,
  identityMode,
  submissionKind,
}: RosterConfirmScreenProps) {
  const [mode, setMode]             = useState<Mode>("confirm");
  const [files, setFiles]           = useState<Record<string, string>>({});
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [loadingFiles, setLoadingFiles] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Complaint form
  const [contactName, setContactName] = useState("");
  const [contactInfo, setContactInfo] = useState("");
  const [note, setNote]               = useState("");
  const [complaintError, setComplaintError] = useState("");

  // Auto-return after complaint_done: 15s silent then 15s countdown
  const COMPLAINT_TOTAL = 30;
  const COMPLAINT_SHOW_AT = 15;
  const [complaintSecondsLeft, setComplaintSecondsLeft] = useState(COMPLAINT_TOTAL);
  useEffect(() => {
    if (mode !== "complaint_done") return;
    setComplaintSecondsLeft(COMPLAINT_TOTAL);
    const interval = setInterval(() => {
      setComplaintSecondsLeft(prev => Math.max(0, prev - 1));
    }, 1000);
    const returnTimer = setTimeout(onBack, COMPLAINT_TOTAL * 1000);
    return () => { clearInterval(interval); clearTimeout(returnTimer); };
  }, [mode, onBack]);

  useEffect(() => {
    loadPreview(initialGithub);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadPreview(github: string) {
    setLoadingFiles(true);
    setFetchError(null);
    try {
      const res = await fetch("/api/exam/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ github_username: github, assignment_name: assignmentName }),
      });
      if (!res.ok) {
        setFetchError(ts(SUB_LOAD_ERROR, submissionKind));
        setFiles({});
        return;
      }
      const data = await res.json();
      setFiles(data.files || {});
      const names = Object.keys(data.files || {});
      setSelectedFile(names[0] || null);
    } catch {
      setFetchError(ts(SUB_NETWORK_ERROR, submissionKind));
      setFiles({});
    } finally {
      setLoadingFiles(false);
    }
  }

  async function handleComplaintSubmit() {
    if (!contactName.trim() || !contactInfo.trim()) return;
    setMode("complaint_sending");
    try {
      // Re-use the existing complaint endpoint — session_id is empty string since exam hasn't started.
      // The note field carries the context.
      const res = await fetch("/api/exam/complaint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          github_username: initialGithub,
          contact_name:    contactName.trim(),
          contact_info:    contactInfo.trim(),
          note: `[PRE-EXAM] assignment=${assignmentName}, github=${initialGithub}. ${note.trim()}`,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setComplaintError(data.error || `שגיאה (${res.status})`);
        setMode("complaint_error");
        return;
      }
      setMode("complaint_done");
    } catch {
      setComplaintError("שגיאת רשת — לא ניתן להגיש את הפנייה.");
      setMode("complaint_error");
    }
  }

  const fileNames = Object.keys(files);

  // ── Complaint done ────────────────────────────────────────────────────────
  if (mode === "complaint_done") {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-gray-950">
        <div className="text-center space-y-4 max-w-sm px-8" dir="rtl">
          <div className="w-14 h-14 rounded-full bg-yellow-900 flex items-center justify-center mx-auto">
            <svg className="w-7 h-7 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-white">הפנייה נרשמה</h2>
          <p className="text-gray-400 text-sm leading-relaxed">
            הצוות האקדמי יצור עמך קשר בהקדם.
          </p>
          {complaintSecondsLeft <= COMPLAINT_SHOW_AT && complaintSecondsLeft > 0 && (
            <p className="text-gray-600 text-xs">
              חוזר למסך הכניסה בעוד {complaintSecondsLeft} שניות…
            </p>
          )}
          <button
            onClick={onBack}
            className="mt-2 px-6 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium rounded-lg transition-colors text-sm"
          >
            חזרה למסך הכניסה
          </button>
        </div>
      </div>
    );
  }

  // ── Main layout ──────────────────────────────────────────────────────────
  return (
    <div className="h-screen w-screen flex bg-gray-950 overflow-hidden">

      {/* Left: confirmation / action panel */}
      <div className="w-80 flex-shrink-0 flex flex-col bg-gray-900 border-r border-gray-800 overflow-y-auto" dir="rtl">

        {/* ── Confirm step ─────────────────────────────────────────────── */}
        {mode === "confirm" && (
          <div className="p-6 space-y-6 flex-1">
            <div className="space-y-1">
              <h2 className="text-lg font-bold text-white">{ts(SUB_CONFIRM_TITLE, submissionKind)}</h2>
              <p className="text-gray-400 text-sm">{ts(SUB_CONFIRM_SUBTITLE, submissionKind)}</p>
            </div>

            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">מטלה:</span>
                <span className="text-gray-200 font-mono">{assignmentName}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">{ti(ID_CONFIRM_LABEL, identityMode)}</span>
                <span className="text-gray-200 font-mono">{initialGithub}</span>
              </div>
            </div>

            <div className="space-y-3">
              <button
                onClick={() => onConfirm(initialGithub)}
                disabled={loadingFiles || fileNames.length === 0}
                className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
              >
                {ts(SUB_CONFIRM_BTN, submissionKind)}
              </button>
              <button
                onClick={onBack}
                className="w-full py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium rounded-lg transition-colors text-sm"
              >
                {ti(ID_WRONG_IDENTIFIER, identityMode)}
              </button>
              <button
                onClick={() => setMode("complaint")}
                className="w-full py-2.5 text-gray-600 hover:text-yellow-500 transition-colors text-sm"
              >
                יש לי בעיה אחרת
              </button>
            </div>

            <button onClick={onBack} className="text-xs text-gray-700 hover:text-gray-500 transition-colors">
              ← חזרה
            </button>
          </div>
        )}

        {/* ── General complaint step ───────────────────────────────────── */}
        {mode === "complaint" && (
          <div className="p-6 space-y-4 flex-1">
            <div className="space-y-1">
              <h2 className="text-lg font-bold text-white">פנייה לצוות האקדמי</h2>
              <p className="text-gray-400 text-sm">
                {ts(SUB_PROBLEM_NOTE, submissionKind)}
              </p>
            </div>
            <div className="p-3 rounded-lg bg-yellow-950 border border-yellow-800 text-yellow-200 text-xs leading-relaxed">
              <strong>שים לב:</strong> לאחר הגשת הפנייה הבחינה לא תתחיל. הצוות יצור עמך קשר ויתאם מועד חלופי.
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setMode("complaint_contact")}
                className="flex-1 py-2.5 bg-yellow-700 hover:bg-yellow-600 text-white font-semibold rounded-lg transition-colors text-sm"
              >
                הגש פנייה
              </button>
              <button
                onClick={() => setMode("confirm")}
                className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium rounded-lg transition-colors text-sm"
              >
                ביטול
              </button>
            </div>
          </div>
        )}

        {/* ── Complaint contact form ───────────────────────────────────── */}
        {mode === "complaint_contact" && (
          <div className="p-6 space-y-4 flex-1">
            <h2 className="text-lg font-bold text-white">פרטי קשר</h2>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">שם מלא *</label>
              <input
                type="text"
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1"> אימייל *</label>
              <input
                type="text"
                value={contactInfo}
                onChange={(e) => setContactInfo(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                dir="ltr"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">תיאור הבעיה</label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleComplaintSubmit}
                disabled={!contactName.trim() || !contactInfo.trim()}
                className="flex-1 py-2.5 bg-yellow-700 hover:bg-yellow-600 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors text-sm"
              >
                שלח פנייה
              </button>
              <button
                onClick={() => setMode("complaint")}
                className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium rounded-lg transition-colors text-sm"
              >
                חזרה
              </button>
            </div>
          </div>
        )}

        {/* ── Sending / error ──────────────────────────────────────────── */}
        {mode === "complaint_sending" && (
          <div className="p-6 flex-1 flex items-center justify-center">
            <p className="text-white animate-pulse">שולח פנייה…</p>
          </div>
        )}

        {mode === "complaint_error" && (
          <div className="p-6 space-y-4 flex-1">
            <p className="text-red-400 font-semibold">שגיאה</p>
            <p className="text-gray-400 text-sm">{complaintError}</p>
            <button
              onClick={() => setMode("complaint_contact")}
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition-colors text-sm"
            >
              נסה שוב
            </button>
          </div>
        )}

      </div>

      {/* Right: code preview */}
      <div className="flex-1 flex flex-col min-w-0 border-l border-gray-800">
        {fileNames.length > 0 && (
          <div className="flex gap-1 px-3 pt-3 flex-wrap bg-gray-900 border-b border-gray-800">
            {fileNames.map((name) => (
              <button
                key={name}
                onClick={() => setSelectedFile(name)}
                className={`px-3 py-1.5 rounded-t text-xs font-mono transition-colors ${
                  selectedFile === name
                    ? "bg-gray-950 text-indigo-300 border border-b-0 border-gray-700"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                {name}
              </button>
            ))}
          </div>
        )}
        {/* min-h-0 is load-bearing: a flex item defaults to min-height:auto, so without it
            this grows to fit the document and the viewer inside can never scroll. */}
        <div className="flex-1 min-h-0 overflow-hidden bg-gray-950" dir="ltr">
          {loadingFiles && <p className="p-4 text-gray-500 animate-pulse text-sm">טוען קוד…</p>}
          {!loadingFiles && fetchError && <p className="p-4 text-red-400 text-sm">{fetchError}</p>}
          {!loadingFiles && !fetchError && fileNames.length === 0 && (
            <p className="p-4 text-gray-600 text-sm">{ti(ID_NO_FILES, identityMode)}</p>
          )}
          {!loadingFiles && selectedFile && files[selectedFile] && (
            submissionKind === "solution" && selectedFile.toLowerCase().endsWith(".md") ? (
              <MarkdownViewer
                content={files[selectedFile]}
                highlightCodeLine={null}
                scrollRevision={0}
              />
            ) : (
              <CodeViewer
                code={files[selectedFile]}
                filename={selectedFile}
                highlightCodeLine={null}
                scrollRevision={0}
              />
            )
          )}
        </div>
      </div>

    </div>
  );
}
