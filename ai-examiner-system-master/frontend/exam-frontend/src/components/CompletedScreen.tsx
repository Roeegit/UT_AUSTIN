"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Language } from "@/lib/welcomeStrings";
import {
  UI_DONE_TITLE, UI_DONE_BODY, UI_TIMEOUT_MSG,
  UI_VIEW_RESULTS, UI_DONE_BTN,
  UI_COMPLAINT_DONE_TITLE, UI_COMPLAINT_DONE_BODY, UI_COMPLAINT_DONE_NOTE,
  UI_DISTRESS_BODY, UI_CLOSE_DOOR,
  t,
} from "@/lib/uiStrings";

interface CompletedScreenProps {
  onReset: () => void;
  sessionId?: string;
  githubUsername?: string;
  persona?: string;
  isTimeout?: boolean;
  isComplaint?: boolean;
  isDistress?: boolean;
  distressMessage?: string | null;
  language?: Language;
}

const DELAY_SECONDS = 15;
const COUNT_SECONDS = 15;
const TOTAL_SECONDS = DELAY_SECONDS + COUNT_SECONDS;

export default function CompletedScreen({
  onReset, sessionId, githubUsername, persona,
  isTimeout, isComplaint, isDistress, distressMessage,
  language = "he",
}: CompletedScreenProps) {
  const router = useRouter();
  const dir = language === "en" ? "ltr" : "rtl";

  const [secondsLeft, setSecondsLeft] = useState(TOTAL_SECONDS);

  useEffect(() => {
    const interval = setInterval(() => {
      setSecondsLeft(prev => Math.max(0, prev - 1));
    }, 1000);
    const returnTimer = setTimeout(onReset, TOTAL_SECONDS * 1000);
    return () => { clearInterval(interval); clearTimeout(returnTimer); };
  }, [onReset]);

  const countdownVisible = secondsLeft <= COUNT_SECONDS && secondsLeft > 0;
  const showResultsButton = !!(sessionId && githubUsername && persona) && !isComplaint && !isDistress;

  function handleViewResults() {
    const params = new URLSearchParams({ student_id: githubUsername!, session_id: sessionId!, persona: persona! });
    router.push(`/qa/results?${params.toString()}`);
  }

  if (isDistress) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-gray-950">
        <div className="text-center space-y-6 max-w-lg px-8" dir={dir}>
          <div className="w-16 h-16 rounded-full bg-blue-900 flex items-center justify-center mx-auto">
            <svg className="w-8 h-8 text-blue-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
          </div>
          {distressMessage && (
            <p className="text-gray-200 text-lg leading-relaxed font-medium">{distressMessage}</p>
          )}
          <p className="text-blue-300 text-base">{t(UI_DISTRESS_BODY, language)}</p>
          {countdownVisible && (
            <p className="text-gray-600 text-xs">
              {language === "en" ? `Returning to start in ${secondsLeft}s…` : `חוזר למסך הכניסה בעוד ${secondsLeft} שניות…`}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (isComplaint) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-gray-950">
        <div className="text-center space-y-6 max-w-md px-8" dir={dir}>
          <div className="w-16 h-16 rounded-full bg-yellow-900 flex items-center justify-center mx-auto">
            <svg className="w-8 h-8 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-white">{t(UI_COMPLAINT_DONE_TITLE, language)}</h1>
          <p className="text-gray-300 text-base leading-relaxed" style={{ whiteSpace: "pre-line" }}>
            {t(UI_COMPLAINT_DONE_BODY, language)}
          </p>
          <p className="text-gray-500 text-sm">{t(UI_COMPLAINT_DONE_NOTE, language)}</p>
          {countdownVisible && (
            <p className="text-gray-600 text-xs">
              {language === "en" ? `Returning to start in ${secondsLeft}s…` : `חוזר למסך הכניסה בעוד ${secondsLeft} שניות…`}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-gray-950">
      <div className="text-center space-y-6 max-w-md px-8" dir={dir}>
        <div className="w-16 h-16 rounded-full bg-green-900 flex items-center justify-center mx-auto">
          <svg className="w-8 h-8 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        {isTimeout && (
          <p className="text-2xl font-semibold text-gray-300">{t(UI_TIMEOUT_MSG, language)}</p>
        )}
        <h1 className="text-3xl font-bold text-white">{t(UI_DONE_TITLE, language)}</h1>
        <p className="text-gray-400 text-lg">{t(UI_DONE_BODY, language)}</p>
        <p className="text-gray-500 text-sm">{t(UI_CLOSE_DOOR, language)}</p>
        <div className="flex flex-col items-center gap-3 mt-4">
          {showResultsButton && (
            <button
              onClick={handleViewResults}
              className="px-8 py-3 bg-emerald-700 hover:bg-emerald-600 text-white font-semibold rounded-lg transition-colors"
            >
              {t(UI_VIEW_RESULTS, language)}
            </button>
          )}
          <button
            onClick={onReset}
            className="px-8 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition-colors"
          >
            {t(UI_DONE_BTN, language)}
          </button>
          {countdownVisible && (
            <p className="text-gray-600 text-xs">
              {language === "en"
                ? `Returning to start in ${secondsLeft}s…`
                : `חוזר למסך הכניסה בעוד ${secondsLeft} שניות…`}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
