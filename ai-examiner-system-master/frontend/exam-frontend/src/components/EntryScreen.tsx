"use client";

import { useEffect, useState } from "react";
import ReportProblemButton from "./ReportProblemButton";
import {
  ID_ENTRY_PROMPT,
  ID_FIELD_LABEL,
  ID_NOT_RECOGNISED,
  ID_PREFILL_NOTE,
  ti,
  type IdentityMode,
} from "@/lib/courseStrings";

interface EntryScreenProps {
  onSubmit: (githubUsername: string) => void;
  isLoading: boolean;
  error?: string | null;
  identityMode: IdentityMode;
  courseTitle: string;
}

const RETURN_DELAY = 20;

export default function EntryScreen({
  onSubmit, isLoading, error, identityMode, courseTitle,
}: EntryScreenProps) {
  const [githubUsername, setGithubUsername] = useState("");
  const [complaintDone, setComplaintDone]   = useState(false);
  const [secondsLeft, setSecondsLeft]       = useState(RETURN_DELAY);

  useEffect(() => {
    if (!complaintDone) return;
    setSecondsLeft(RETURN_DELAY);
    const interval = setInterval(() => setSecondsLeft(s => Math.max(0, s - 1)), 1000);
    const timer    = setTimeout(() => { setComplaintDone(false); }, RETURN_DELAY * 1000);
    return () => { clearInterval(interval); clearTimeout(timer); };
  }, [complaintDone]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!githubUsername.trim()) return;
    onSubmit(githubUsername.trim());
  }

  if (complaintDone) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-gray-950">
        <div className="text-center space-y-4 max-w-sm px-8" dir="rtl">
          <div className="w-14 h-14 rounded-full bg-yellow-900 flex items-center justify-center mx-auto">
            <svg className="w-7 h-7 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-white">הפנייה נרשמה</h2>
          <p className="text-gray-400 text-sm">הצוות האקדמי יצור עמך קשר בהקדם.</p>
          <p className="text-gray-600 text-xs">חוזר למסך הכניסה בעוד {secondsLeft} שניות…</p>
          <button
            onClick={() => setComplaintDone(false)}
            className="mt-2 px-6 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition-colors"
          >
            חזרה עכשיו
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-gray-950">
      <div className="w-full max-w-sm bg-gray-900 rounded-xl p-8 shadow-2xl border border-gray-800">
        <h1 className="text-xl font-semibold text-gray-100 text-center mb-1" dir="rtl">
          {courseTitle}
        </h1>
        <p className="text-sm text-gray-500 text-center mb-8" dir="rtl">
          {ti(ID_ENTRY_PROMPT, identityMode)}
        </p>

        <form onSubmit={handleSubmit} className="space-y-5" dir="ltr">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1 text-right" dir="rtl">
              {ti(ID_FIELD_LABEL, identityMode)}
            </label>
            <input
              type="text"
              value={githubUsername}
              onChange={(e) => setGithubUsername(e.target.value)}
              disabled={isLoading}
              autoFocus
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:opacity-50"
            />
          </div>

          {error && (
            <p className="text-red-400 text-sm text-right" dir="rtl">{error}</p>
          )}

          <button
            type="submit"
            disabled={isLoading || !githubUsername.trim()}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-900 disabled:text-indigo-500 text-white font-semibold py-3 rounded-lg transition-colors mt-2"
          >
            {isLoading ? "מאחזר…" : "המשך"}
          </button>
        </form>

        <div className="mt-6 text-center" dir="rtl">
          <ReportProblemButton
            language="he"
            labelOverride={ti(ID_NOT_RECOGNISED, identityMode)}
            prefillNote={ti(ID_PREFILL_NOTE, identityMode)}
            suppressBlockingWarning
            onSubmitted={() => setComplaintDone(true)}
            buttonClassName="text-sm text-gray-400 hover:text-yellow-300 transition-colors underline underline-offset-2 bg-transparent border-0 cursor-pointer"
          />
        </div>

      </div>
    </div>
  );
}
