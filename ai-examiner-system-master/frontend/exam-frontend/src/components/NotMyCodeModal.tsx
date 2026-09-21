"use client";

import { useState } from "react";
import type { Language } from "@/lib/welcomeStrings";
import {
  UI_MODAL_TITLE, UI_MODAL_CONFIRM_Q, UI_MODAL_WARNING,
  UI_MODAL_CONFIRM_BTN, UI_MODAL_CANCEL,
  UI_MODAL_CONTACT_TITLE, UI_MODAL_CONTACT_SUB,
  UI_MODAL_FULL_NAME, UI_MODAL_PHONE_EMAIL, UI_MODAL_NOTE, UI_MODAL_NOTE_PH,
  UI_MODAL_SEND, UI_MODAL_BACK,
  UI_MODAL_SENDING, UI_MODAL_SUCCESS, UI_MODAL_REDIRECT,
  UI_MODAL_ERROR_TITLE, UI_MODAL_RETRY, UI_MODAL_CANCEL as UI_MODAL_CANCEL2,
  t,
} from "@/lib/uiStrings";

interface NotMyCodeModalProps {
  sessionId: string;
  onComplaintSubmitted: () => void;
  onClose: () => void;
  language?: Language;
}

type Step = "confirm" | "contact" | "submitting" | "done" | "error";

export default function NotMyCodeModal({ sessionId, onComplaintSubmitted, onClose, language = "he" }: NotMyCodeModalProps) {
  const [step, setStep] = useState<Step>("confirm");
  const [contactName, setContactName] = useState("");
  const [contactInfo, setContactInfo] = useState("");
  const [note, setNote] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const dir = language === "en" ? "ltr" : "rtl";

  async function handleSubmit() {
    if (!contactName.trim() || !contactInfo.trim()) return;
    setStep("submitting");
    try {
      const res = await fetch("/api/exam/complaint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          contact_name: contactName.trim(),
          contact_info: contactInfo.trim(),
          note: note.trim(),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setErrorMsg(data.error || `Error (${res.status})`);
        setStep("error");
        return;
      }
      setStep("done");
      setTimeout(() => onComplaintSubmitted(), 1500);
    } catch {
      setErrorMsg(language === "en" ? "Network error — could not submit complaint." : "שגיאת רשת — לא ניתן להגיש את הפנייה.");
      setStep("error");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" dir={dir}>
      <div className="w-full max-w-md bg-gray-900 rounded-2xl p-8 shadow-2xl border border-gray-700 space-y-6 mx-4">

        {step === "confirm" && (
          <>
            <div className="space-y-2">
              <h2 className="text-xl font-bold text-white">{t(UI_MODAL_TITLE, language)}</h2>
              <p className="text-gray-300 text-sm leading-relaxed">{t(UI_MODAL_CONFIRM_Q, language)}</p>
              <div className="mt-3 p-4 rounded-lg bg-yellow-950 border border-yellow-800 text-yellow-200 text-sm leading-relaxed">
                {t(UI_MODAL_WARNING, language)}
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setStep("contact")}
                className="flex-1 py-2.5 bg-yellow-700 hover:bg-yellow-600 text-white font-semibold rounded-lg transition-colors"
              >
                {t(UI_MODAL_CONFIRM_BTN, language)}
              </button>
              <button
                onClick={onClose}
                className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-300 font-semibold rounded-lg transition-colors"
              >
                {t(UI_MODAL_CANCEL, language)}
              </button>
            </div>
          </>
        )}

        {step === "contact" && (
          <>
            <div className="space-y-2">
              <h2 className="text-xl font-bold text-white">{t(UI_MODAL_CONTACT_TITLE, language)}</h2>
              <p className="text-gray-400 text-sm">{t(UI_MODAL_CONTACT_SUB, language)}</p>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">{t(UI_MODAL_FULL_NAME, language)}</label>
                <input
                  type="text"
                  value={contactName}
                  onChange={(e) => setContactName(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  dir={dir}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">{t(UI_MODAL_PHONE_EMAIL, language)}</label>
                <input
                  type="text"
                  value={contactInfo}
                  onChange={(e) => setContactInfo(e.target.value)}
                  placeholder="050-0000000 / student@biu.ac.il"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  dir="ltr"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">{t(UI_MODAL_NOTE, language)}</label>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={t(UI_MODAL_NOTE_PH, language)}
                  rows={3}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-gray-100 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  dir={dir}
                />
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleSubmit}
                disabled={!contactName.trim() || !contactInfo.trim()}
                className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
              >
                {t(UI_MODAL_SEND, language)}
              </button>
              <button
                onClick={() => setStep("confirm")}
                className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-300 font-semibold rounded-lg transition-colors"
              >
                {t(UI_MODAL_BACK, language)}
              </button>
            </div>
          </>
        )}

        {step === "submitting" && (
          <div className="text-center py-6 space-y-3">
            <p className="text-white text-lg animate-pulse">{t(UI_MODAL_SENDING, language)}</p>
          </div>
        )}

        {step === "done" && (
          <div className="text-center py-4 space-y-3">
            <div className="w-12 h-12 rounded-full bg-green-900 flex items-center justify-center mx-auto">
              <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-white font-semibold">{t(UI_MODAL_SUCCESS, language)}</p>
            <p className="text-gray-400 text-sm">{t(UI_MODAL_REDIRECT, language)}</p>
          </div>
        )}

        {step === "error" && (
          <>
            <div className="space-y-2">
              <h2 className="text-xl font-bold text-red-400">{t(UI_MODAL_ERROR_TITLE, language)}</h2>
              <p className="text-gray-300 text-sm">{errorMsg}</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setStep("contact")}
                className="flex-1 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition-colors"
              >
                {t(UI_MODAL_RETRY, language)}
              </button>
              <button
                onClick={onClose}
                className="flex-1 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-300 font-semibold rounded-lg transition-colors"
              >
                {t(UI_MODAL_CANCEL2, language)}
              </button>
            </div>
          </>
        )}

      </div>
    </div>
  );
}
