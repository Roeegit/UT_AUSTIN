"use client";

import { useState, useEffect, useRef } from "react";
import type { Language } from "@/lib/welcomeStrings";
import { UI_ANSWER_PLACEHOLDER, UI_SUBMIT_BUTTON, UI_SUBMITTING, t } from "@/lib/uiStrings";
import ReportProblemButton from "./ReportProblemButton";

interface AnswerInputProps {
  isSubmitting: boolean;
  onSubmit: (text: string) => void;
  questionNumber: number;
  language?: Language;
  sessionId?: string;
  onComplaintSubmitted?: () => void;
  registerAnswerGetter?: (getter: () => string) => void;
}

export default function AnswerInput({ isSubmitting, onSubmit, questionNumber, language = "he", sessionId, onComplaintSubmitted, registerAnswerGetter }: AnswerInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Register a getter so the timeout handler can read the current value without per-keystroke tracking
  useEffect(() => {
    registerAnswerGetter?.(() => textareaRef.current?.value ?? "");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-focus and clear when question changes
  useEffect(() => {
    setValue("");
    textareaRef.current?.focus();
  }, [questionNumber]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed || isSubmitting) return;
    onSubmit(trimmed);
  }

  const dir = language === "en" ? "ltr" : "rtl";
  const textAlign = language === "en" ? "text-left" : "text-right";

  return (
    <div className="flex flex-col gap-3">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={isSubmitting}
        placeholder={t(UI_ANSWER_PLACEHOLDER, language)}
        rows={6}
        dir="auto"
        className={`w-full resize-none rounded-lg bg-gray-900 border border-gray-700 text-gray-100 placeholder-gray-600 px-4 py-3 text-base focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${textAlign}`}
        style={{ unicodeBidi: "plaintext" }}
      />
      <div className="flex items-center justify-between" dir={dir}>
        <ReportProblemButton language={language} sessionId={sessionId} onSubmitted={onComplaintSubmitted} />
        <div className="flex items-center gap-3">
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || !value.trim()}
            className="px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white text-sm font-semibold transition-colors flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                {t(UI_SUBMITTING, language)}
              </>
            ) : (
              t(UI_SUBMIT_BUTTON, language)
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
