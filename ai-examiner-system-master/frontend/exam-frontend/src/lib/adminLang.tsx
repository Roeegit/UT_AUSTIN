"use client";

/**
 * adminLang.tsx — admin-wide language state (he ⇄ en).
 *
 * The choice is per-viewer, persisted in localStorage, and applies to every /admin page.
 * It is independent of the student-facing exam language (Session.language) — this only
 * controls the staff UI chrome.
 *
 * Direction flips with the language, so admin pages must read `dir` from here rather than
 * hardcoding dir="rtl", and should use Tailwind's logical utilities (ps-N, pe-N, text-start,
 * text-end, ms-N, me-N) so tables and spacing mirror correctly.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { Language } from "./welcomeStrings";
import { A_LANG_TOGGLE_TITLE, t } from "./adminStrings";

const STORAGE_KEY = "admin_lang";

interface AdminLangValue {
  lang: Language;
  dir: "rtl" | "ltr";
  /** Date/number locale matching the current language. */
  locale: string;
  setLang: (l: Language) => void;
  toggle: () => void;
}

const AdminLangContext = createContext<AdminLangValue>({
  lang: "he",
  dir: "rtl",
  locale: "he-IL",
  setLang: () => {},
  toggle: () => {},
});

export function AdminLangProvider({ children }: { children: React.ReactNode }) {
  // Always start on "he" so the server-rendered markup matches the first client render;
  // the stored preference is applied in the effect below to avoid a hydration mismatch.
  const [lang, setLangState] = useState<Language>("he");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "he" || stored === "en") setLangState(stored);
  }, []);

  const setLang = useCallback((l: Language) => {
    setLangState(l);
    localStorage.setItem(STORAGE_KEY, l);
  }, []);

  const toggle = useCallback(() => {
    setLangState((prev) => {
      const next: Language = prev === "he" ? "en" : "he";
      localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const value: AdminLangValue = {
    lang,
    dir: lang === "he" ? "rtl" : "ltr",
    locale: lang === "he" ? "he-IL" : "en-US",
    setLang,
    toggle,
  };

  return <AdminLangContext.Provider value={value}>{children}</AdminLangContext.Provider>;
}

export function useAdminLang(): AdminLangValue {
  return useContext(AdminLangContext);
}

/**
 * The he/en switch. Shows both options with the active one highlighted, so it's obvious
 * what the control does before you click it.
 */
export function AdminLangToggle({ className = "" }: { className?: string }) {
  const { lang, setLang } = useAdminLang();

  const btn = (target: Language, label: string) => (
    <button
      type="button"
      onClick={() => setLang(target)}
      aria-pressed={lang === target}
      className={`px-2.5 py-1 rounded-md transition-colors ${
        lang === target
          ? "bg-gray-700 text-white"
          : "text-gray-500 hover:text-gray-300"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div
      dir="ltr"
      title={t(A_LANG_TOGGLE_TITLE, lang)}
      className={`inline-flex items-center gap-0.5 rounded-lg border border-gray-800 bg-gray-900 p-0.5 text-xs font-medium ${className}`}
    >
      {btn("en", "EN")}
      {btn("he", "עב")}
    </div>
  );
}
