"use client";

import { useState } from "react";
import type { Gender, Language } from "@/lib/welcomeStrings";

interface PreferencesScreenProps {
  onConfirm: (gender: Gender, language: Language) => void;
}

export default function PreferencesScreen({ onConfirm }: PreferencesScreenProps) {
  const [gender, setGender]     = useState<Gender | null>(null);
  const [language, setLanguage] = useState<Language | null>(null);

  const ready = gender !== null && language !== null;

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-sm bg-gray-900 rounded-xl p-8 shadow-2xl border border-gray-800 space-y-8">

        <div className="text-center space-y-1">
          <h2 className="text-xl font-semibold text-white">העדפות אישיות</h2>
          <p className="text-gray-500 text-sm">Personal preferences</p>
        </div>

        {/* Gender */}
        <div className="space-y-3" dir="rtl">
          <p className="text-sm font-medium text-gray-300">
            באיזו צורת פנייה תרגיש בנוח?
          </p>
          <div className="grid grid-cols-2 gap-3">
            {(["male", "female"] as Gender[]).map((g) => (
              <button
                key={g}
                onClick={() => setGender(g)}
                className={`py-2.5 rounded-lg border-2 font-semibold text-sm transition-all ${
                  gender === g
                    ? "border-indigo-500 bg-indigo-950 text-white"
                    : "border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-500"
                }`}
              >
                {g === "male" ? "זכר" : "נקבה"}
              </button>
            ))}
          </div>
        </div>

        {/* Language */}
        <div className="space-y-3" dir="rtl">
          <p className="text-sm font-medium text-gray-300">
            באיזה שפה תרצה להמשיך?
          </p>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => setLanguage("he")}
              className={`py-2.5 rounded-lg border-2 font-semibold text-sm transition-all ${
                language === "he"
                  ? "border-indigo-500 bg-indigo-950 text-white"
                  : "border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-500"
              }`}
            >
              עברית
            </button>
            <button
              onClick={() => setLanguage("en")}
              className={`py-2.5 rounded-lg border-2 font-semibold text-sm transition-all ${
                language === "en"
                  ? "border-indigo-500 bg-indigo-950 text-white"
                  : "border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-500"
              }`}
            >
              English
            </button>
          </div>
        </div>

        <button
          disabled={!ready}
          onClick={() => ready && onConfirm(gender!, language!)}
          className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
        >
          המשך / Continue
        </button>

      </div>
    </div>
  );
}
