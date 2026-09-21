"use client";

import { useState } from "react";
import type { Language } from "@/lib/welcomeStrings";

interface ReportProblemButtonProps {
  language?: Language;
  sessionId?: string;
  githubUsername?: string;
  onSubmitted?: () => void;
  prefillNote?: string;
  suppressBlockingWarning?: boolean;
  buttonClassName?: string;
  labelOverride?: string;
}

export default function ReportProblemButton({
  language = "he",
  sessionId,
  githubUsername,
  onSubmitted,
  prefillNote = "",
  suppressBlockingWarning = false,
  buttonClassName,
  labelOverride,
}: ReportProblemButtonProps) {
  const [open, setOpen]               = useState(false);
  const [contactName, setContactName] = useState("");
  const [contactInfo, setContactInfo] = useState("");
  const [note, setNote]               = useState(prefillNote);
  const [status, setStatus]           = useState<"idle" | "sending" | "done" | "error">("idle");
  const [errMsg, setErrMsg]           = useState("");

  const label = labelOverride ?? (language === "en" ? "Report a problem" : "דווח על בעיה");
  const dir   = language === "en" ? "ltr" : "rtl";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!contactName.trim() || !contactInfo.trim()) return;
    setStatus("sending");
    try {
      const res = await fetch("/api/exam/complaint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id:      sessionId  || null,
          github_username: githubUsername || null,
          contact_name:    contactName.trim(),
          contact_info:    contactInfo.trim(),
          note:            note.trim(),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setErrMsg(data.detail || `Error ${res.status}`);
        setStatus("error");
        return;
      }
      setStatus("done");
    } catch {
      setErrMsg("Network error — please try again.");
      setStatus("error");
    }
  }

  function handleClose() {
    setOpen(false);
    setStatus("idle");
    setContactName("");
    setContactInfo("");
    setNote(prefillNote);
    setErrMsg("");
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={buttonClassName ?? "px-4 py-2 bg-gray-800 hover:bg-yellow-900 border border-gray-700 hover:border-yellow-700 text-gray-400 hover:text-yellow-300 font-medium rounded-lg transition-colors text-sm"}
      >
        {label}
      </button>

      {open && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-full max-w-sm p-6" dir={dir}>

            {status === "done" ? (
              <div className="text-center space-y-4">
                <p className="text-white font-semibold text-lg">
                  {language === "en" ? "Report submitted" : "הפנייה נרשמה"}
                </p>
                <p className="text-gray-400 text-sm">
                  {language === "en"
                    ? "The academic team will contact you soon."
                    : "הצוות האקדמי יצור עמך קשר בהקדם."}
                </p>
                <button
                  onClick={() => { handleClose(); onSubmitted?.(); }}
                  className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition-colors text-sm"
                >
                  {language === "en" ? "Close" : "סגור"}
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <h2 className="text-white font-bold text-lg">{label}</h2>

                {!suppressBlockingWarning && (
                  <div className="p-3 rounded-lg bg-yellow-950 border border-yellow-700 text-yellow-200 text-xs leading-relaxed">
                    {language === "en"
                      ? "⚠️ Submitting this report will immediately halt your session. You will not be able to continue or start a new session until a faculty member manually reviews your case."
                      : "⚠️ הגשת הפנייה תעצור את ההערכה באופן מיידי. לא תוכל להמשיך או לפתוח סשן חדש עד שאחד מחברי הסגל יבדוק את הפנייה ידנית."}
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    {language === "en" ? "Full name *" : "שם מלא *"}
                  </label>
                  <input
                    type="text"
                    value={contactName}
                    onChange={(e) => setContactName(e.target.value)}
                    disabled={status === "sending"}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    {language === "en" ? "Email *" : "אימייל *"}
                  </label>
                  <input
                    type="text"
                    value={contactInfo}
                    onChange={(e) => setContactInfo(e.target.value)}
                    disabled={status === "sending"}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    dir="ltr"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-400 mb-1">
                    {language === "en" ? "Description" : "תיאור הבעיה"}
                  </label>
                  <textarea
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    disabled={status === "sending"}
                    rows={3}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  />
                </div>

                {status === "error" && (
                  <p className="text-red-400 text-xs">{errMsg}</p>
                )}

                <div className="flex gap-2">
                  <button
                    type="submit"
                    disabled={!contactName.trim() || !contactInfo.trim() || status === "sending"}
                    className="flex-1 py-2.5 bg-yellow-700 hover:bg-yellow-600 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors text-sm"
                  >
                    {status === "sending"
                      ? (language === "en" ? "Sending…" : "שולח…")
                      : (language === "en" ? "Submit" : "שלח")}
                  </button>
                  <button
                    type="button"
                    onClick={handleClose}
                    disabled={status === "sending"}
                    className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium rounded-lg transition-colors text-sm"
                  >
                    {language === "en" ? "Cancel" : "ביטול"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}
