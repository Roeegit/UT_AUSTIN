"use client";

import { useState } from "react";
import {
  Gender,
  Language,
  WELCOME_TITLE,
  WELCOME_TITLE_BARE,
  WELCOME_SUBTITLE,
  BULLET_AI,
  BULLET_LAYOUT,
  BULLET_ANSWER,
  BULLET_TIMER,
  BULLET_NO_BACK,
  BULLET_NO_CHAT,
  BULLET_SWITCH,
  BULLET_RELAX,
  FOOTER_GOOD_LUCK,
  FOOTER_START_BTN,
  pick,
} from "@/lib/welcomeStrings";

interface WelcomeScreenProps {
  onStart: () => void;
  examDurationMinutes: number;
  gender: Gender;
  language: Language;
  assignmentLabel?: string;
}

/** Renders a bullet with an icon and HTML content (bold tags only — no user input). */
function Bullet({ icon, html }: { icon: string; html: string }) {
  return (
    <div className="flex gap-3 items-start">
      <span className="text-indigo-400 text-xl mt-0.5">{icon}</span>
      {/* dangerouslySetInnerHTML is safe here — html comes entirely from our own constants */}
      <p dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}

export default function WelcomeScreen({ onStart, examDurationMinutes, gender, language, assignmentLabel }: WelcomeScreenProps) {
  const dir = language === "he" ? "rtl" : "ltr";
  const [agreed, setAgreed] = useState(false);

  const title = assignmentLabel
    ? pick(WELCOME_TITLE, gender, language).replace("{assignment}", assignmentLabel)
    : pick(WELCOME_TITLE_BARE, gender, language);

  const timerHtml = pick(BULLET_TIMER, gender, language).replace(
    "{minutes}",
    `${examDurationMinutes}`
  );

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-gray-950 px-4" dir={dir}>
      <div className="w-full max-w-2xl bg-gray-900 rounded-2xl p-10 shadow-2xl border border-gray-800 space-y-8">

        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold text-white">{title}</h1>
          <p className="text-gray-400 text-base">{pick(WELCOME_SUBTITLE, gender, language)}</p>
        </div>

        {/* Explanation bullets */}
        <div className="space-y-4 text-gray-300 text-sm leading-relaxed">
          <Bullet icon="🤖" html={pick(BULLET_AI, gender, language)} />
          <Bullet icon="💻" html={pick(BULLET_LAYOUT, gender, language)} />
          <Bullet icon="✍️" html={pick(BULLET_ANSWER, gender, language)} />
          <Bullet icon="💬" html={pick(BULLET_NO_CHAT, gender, language)} />
          <Bullet icon="⏱️" html={timerHtml} />
          <Bullet icon="🚫" html={pick(BULLET_NO_BACK, gender, language)} />
          <Bullet icon="🔄" html={pick(BULLET_SWITCH, gender, language)} />
          <Bullet icon="🙏" html={pick(BULLET_RELAX, gender, language)} />
          <Bullet icon="📷" html="תשומת ליבך וידיעתך כי בעת המבדק הינך מצולם באמצעות 2 מצלמות כמקובל בבחינות באמצעות מערכת התומקס. האוניברסיטה רשאית להשתמש בצילומים לצרכי הערכת אמינות המבדק, עמידתך בהוראות ושמירה על טוהר המבדק." />
        </div>

        {/* Consent checkbox */}
        <label className="flex items-center gap-3 cursor-pointer select-none" dir="rtl">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            className="w-5 h-5 rounded border-gray-600 bg-gray-800 accent-indigo-500 cursor-pointer flex-shrink-0"
          />
          <span className="text-gray-300 text-sm">קראתי, הבנתי ואני מסכים להוראות לעיל</span>
        </label>

        {/* Divider */}
        <div className="border-t border-gray-700" />

        {/* Footer */}
        <div className="text-center space-y-4">
          <p className="text-gray-400 text-sm">{pick(FOOTER_GOOD_LUCK, gender, language)}</p>
          <button
            onClick={onStart}
            disabled={!agreed}
            className={`px-12 py-3 font-semibold rounded-lg text-base transition-colors shadow-lg text-white ${
              agreed
                ? "bg-indigo-600 hover:bg-indigo-500 cursor-pointer"
                : "bg-gray-700 cursor-not-allowed opacity-50"
            }`}
          >
            {pick(FOOTER_START_BTN, gender, language)}
          </button>
        </div>

      </div>
    </div>
  );
}
