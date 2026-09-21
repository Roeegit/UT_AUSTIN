/**
 * adminStrings.ts — bilingual UI strings for the /admin pages.
 *
 * Same shape as uiStrings.ts: every string is a { he, en } pair, resolved with `t()`.
 * The admin language is chosen per-viewer via the toggle in the admin header
 * (see lib/adminLang.tsx) — it is independent of the student-facing exam language.
 *
 * NOTE: this covers UI chrome only. Grader-produced content (professor report, student
 * feedback, code-review notes) is stored in whatever language it was generated in and is
 * rendered with dir="auto" so it reads correctly either way.
 */

import type { Language } from "./welcomeStrings";

type S = Record<Language, string>;

const s = (he: string, en: string): S => ({ he, en });

export function t(strings: S, lang: Language): string {
  return strings[lang] ?? strings.he;
}

/** Fill {placeholders} in a resolved string. */
export function tf(strings: S, lang: Language, vars: Record<string, string | number>): string {
  return Object.entries(vars).reduce(
    (acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)),
    t(strings, lang),
  );
}

// ── Generic ───────────────────────────────────────────────────────────────────
export const A_BACK:            S = s("חזרה",                 "Back");
export const A_ERROR:           S = s("שגיאה",                "Error");
export const A_ERROR_N:         S = s("שגיאה {n}",            "Error {n}");
export const A_NETWORK_ERROR:   S = s("שגיאת רשת",            "Network error");
export const A_NETWORK_ERROR_D: S = s("שגיאת רשת: {detail}",  "Network error: {detail}");
export const A_ERROR_DETAIL:    S = s("שגיאה: {detail}",      "Error: {detail}");
export const A_NO_DATA:         S = s("לא נמצאו נתונים",      "No data found");
export const A_NONE:            S = s("אין",                  "None");
export const A_OPEN:            S = s("▼ פתח",                "▼ Open");
export const A_CLOSE:           S = s("▲ סגור",               "▲ Close");
export const A_CLOSE_BTN:       S = s("סגור",                 "Close");
export const A_CANCEL:          S = s("ביטול",                "Cancel");
export const A_SENDING:         S = s("שולח...",              "Sending…");

// ── Login ─────────────────────────────────────────────────────────────────────
export const A_LOGIN_TITLE:     S = s("מסך ניהול",                    "Admin");
export const A_LOGIN_SUB:       S = s("הזן סיסמת צפייה כדי להמשיך",   "Enter the viewer password to continue");
export const A_PASSWORD:        S = s("סיסמה",                        "Password");
export const A_BAD_PASSWORD:    S = s("סיסמה שגויה",                  "Incorrect password");
export const A_LOGIN_UNAVAIL:   S = s("השרת החזיר שגיאה {n} — לא ניתן לאמת את הסיסמה כעת",
                                      "The server returned error {n} — cannot verify the password right now");
export const A_NET_RETRY:       S = s("שגיאת רשת — נסה שוב",          "Network error — please try again");
export const A_SIGNING_IN:      S = s("מתחבר...",                     "Signing in…");
export const A_SIGN_IN:         S = s("כניסה",                        "Sign in");
export const A_SIGN_OUT:        S = s("התנתק",                        "Sign out");

// ── Admin home ────────────────────────────────────────────────────────────────
export const A_HOME_TITLE:      S = s("מסך ניהול — תוצאות בחינות",    "Admin — Exam Results");
export const A_LOADING_ASSIGN:  S = s("טוען מטלות...",                "Loading assignments…");
export const A_NO_ASSIGNMENTS:  S = s("אין מטלות זמינות",             "No assignments available");
export const A_PICK_ASSIGNMENT: S = s("בחר מטלה...",                  "Select an assignment…");
export const A_FIND_STUDENT:    S = s("חיפוש סטודנט",                 "Find a student");
// Identifier-neutral: a student is keyed by a GitHub username in Operating Systems and by a
// 9-digit university ID in a Forms course, and one admin build serves both.
export const A_STUDENT_IDENTIFIER: S = s("שם משתמש או ת.ז.",           "Username or ID");
export const A_VIEW_STUDENT:    S = s("צפה בתוצאות הסטודנט",          "View student results");
export const A_ASSIGN_OVERVIEW: S = s("סקירת מטלה",                   "Assignment overview");
export const A_OVERVIEW_BTN:    S = s("סקירה כללית",                  "Open overview");

// ── Invalidate exam ───────────────────────────────────────────────────────────
export const A_INVALIDATE_TITLE: S = s("ביטול בחינה",                        "Invalidate exam");
export const A_LOADING_SESSIONS: S = s("טוען סשנים...",                      "Loading sessions…");
export const A_NO_SESSIONS:      S = s("לא נמצאו סשנים עבור משתמש זה.",      "No sessions found for this user.");
export const A_CURRENT_STATUS:   S = s("סטטוס נוכחי:",                       "Current status:");
export const A_INVALIDATE_BTN:   S = s("בטל בחינה",                          "Invalidate exam");
export const A_INVALIDATING:     S = s("מבטל...",                            "Invalidating…");
export const A_ENABLE_RETAKE:    S = s("אפשר מבחן חוזר",                     "Enable retake");
export const A_ENABLING:         S = s("מאפשר...",                           "Enabling…");
export const A_INVALIDATED_OK:   S = s("בוטלו {n} סשנים בהצלחה.",            "Invalidated {n} session(s).");
export const A_RETAKE_OK:        S = s("אופשר מבחן חוזר ל-{n} סשנים בהצלחה.", "Retake enabled for {n} session(s).");

// ── Authorship ────────────────────────────────────────────────────────────────
export const A_AUTH_ESTABLISHED:     S = s("בעלות מוכחת",      "Authorship established");
export const A_AUTH_PARTIAL:         S = s("בעלות חלקית",      "Authorship partial");
export const A_AUTH_NOT_ESTABLISHED: S = s("בעלות לא מוכחת",   "Authorship not established");
export const A_AUTH_UNKNOWN:         S = s("לא ידוע",          "Unknown");

export const AUTHORSHIP_LABELS: Record<string, S> = {
  established:     A_AUTH_ESTABLISHED,
  partial:         A_AUTH_PARTIAL,
  not_established: A_AUTH_NOT_ESTABLISHED,
  unknown:         A_AUTH_UNKNOWN,
};

// ── ID resolution ─────────────────────────────────────────────────────────────
/** Long inline notices shown on the student detail page. */
export const ID_NOTICES: Record<string, { text: S; color: string }> = {
  ok:                      { text: s("", ""), color: "" },
  ok_9_digits:             { text: s("9 ספרות — לא אומת מול הרשימה",            "9 digits — not verified against the roster"), color: "text-amber-400 bg-amber-900/30" },
  ok_5_digits:             { text: s("5 ספרות — לא אומת מול הרשימה",            "5 digits — not verified against the roster"), color: "text-amber-400 bg-amber-900/30" },
  name_not_in_roster:      { text: s("מספר זיהוי לא נמצא ברשימת הכיתה",         "ID number not found in the class roster"),    color: "text-red-400 bg-red-900/30" },
  ambiguous_5_digit_match: { text: s("5 ספרות אחרונות תואמות יותר מסטודנט אחד", "Last 5 digits match more than one student"),  color: "text-red-400 bg-red-900/30" },
  missing_file:            { text: s("קובץ id.txt לא נמצא ב-GitHub",            "id.txt not found on GitHub"),                 color: "text-yellow-400 bg-yellow-900/30" },
  empty_file:              { text: s("קובץ id.txt ריק",                         "id.txt is empty"),                            color: "text-yellow-400 bg-yellow-900/30" },
  no_digits:               { text: s("id.txt אינו מכיל ספרות",                  "id.txt contains no digits"),                  color: "text-yellow-400 bg-yellow-900/30" },
  wrong_length:            { text: s("id.txt מכיל מספר ספרות שגוי",             "id.txt has the wrong number of digits"),      color: "text-yellow-400 bg-yellow-900/30" },
  fetch_error:             { text: s("שגיאה בטעינת id.txt",                     "Failed to load id.txt"),                      color: "text-yellow-400 bg-yellow-900/30" },
  // Resolved by a fallback rather than id.txt — worth surfacing, but not a problem.
  ok_via_prior_blob:             { text: s("זוהה לפי מטלה קודמת של אותו סטודנט",   "Identified from this student's earlier assignment"), color: "text-sky-400 bg-sky-900/30" },
  ok_via_secondary_username_map: { text: s("זוהה לפי מיפוי משתמשים משני",          "Identified via the secondary username map"),         color: "text-sky-400 bg-sky-900/30" },
  ok_via_classroom_roster:       { text: s("זוהה לפי רשימת הכיתה",                 "Identified via the classroom roster"),               color: "text-sky-400 bg-sky-900/30" },
  manual_correction:             { text: s("תוקן ידנית על ידי הצוות",              "Manually corrected by staff"),                       color: "text-sky-400 bg-sky-900/30" },
  // Fallbacks that did not fully resolve.
  roster_name_not_in_id_map:      { text: s("נמצא ברשימת הכיתה אך לא במיפוי ת\"ז",  "Found in the roster but not in the ID map"),        color: "text-red-400 bg-red-900/30" },
  secondary_map_id_not_in_roster: { text: s("מיפוי משני מצא ת\"ז שאינה ברשימה",     "Secondary map found an ID that is not in the roster"), color: "text-red-400 bg-red-900/30" },
  secondary_map_ambiguous:        { text: s("מיפוי משני החזיר התאמה דו-משמעית",     "Secondary map returned an ambiguous match"),        color: "text-red-400 bg-red-900/30" },
};

/**
 * Short labels used in the assignment-overview breakdown.
 *
 * Covers every status main.py can emit during the Phase-3 name-resolution chain
 * (id.txt → prior blob → secondary username map → classroom roster). Anything not
 * listed here falls back to the raw key.
 */
export const ID_STATUS_LABELS: Record<string, S> = {
  // resolved from id.txt
  ok:                            s("אומת ✓",                    "Verified ✓"),
  ok_9_digits:                   s("9 ספרות (לא אומת)",         "9 digits (unverified)"),
  ok_5_digits:                   s("5 ספרות (לא אומת)",         "5 digits (unverified)"),
  // resolved by a fallback in the chain
  ok_via_prior_blob:             s("אומת ממטלה קודמת",          "Verified via earlier assignment"),
  ok_via_secondary_username_map: s("אומת ממיפוי משתמשים משני",  "Verified via secondary username map"),
  ok_via_classroom_roster:       s("אומת מרשימת הכיתה",         "Verified via classroom roster"),
  manual_correction:             s("תוקן ידנית",                "Manually corrected"),
  // unresolved
  name_not_in_roster:            s("לא ברשימה",                 "Not in roster"),
  roster_name_not_in_id_map:     s("ברשימה אך לא במיפוי ת\"ז",  "In roster, not in ID map"),
  secondary_map_id_not_in_roster: s("מיפוי משני — לא ברשימה",   "Secondary map — not in roster"),
  secondary_map_ambiguous:       s("מיפוי משני — דו-משמעי",     "Secondary map — ambiguous"),
  ambiguous_5_digit_match:       s("דו-משמעי",                  "Ambiguous"),
  missing_file:                  s("id.txt חסר",                "id.txt missing"),
  empty_file:                    s("id.txt ריק",                "id.txt empty"),
  no_digits:                     s("ללא ספרות",                 "No digits"),
  wrong_length:                  s("אורך שגוי",                 "Wrong length"),
  fetch_error:                   s("שגיאת טעינה",               "Fetch error"),
  unknown:                       s("לא ידוע",                   "Unknown"),
};

// ── Student detail ────────────────────────────────────────────────────────────
export const A_MISSING_ASSIGNMENT: S = s("חסר פרמטר assignment בכתובת",   "Missing 'assignment' query parameter");
export const A_TIMED_OUT:          S = s("נגמר הזמן",                     "Timed out");
export const A_SHORT_ID:           S = s('ת"ז קצרה:',                     "Short ID:");
export const A_SHOW_FULL_ID:       S = s('הצג ת"ז מלאה',                  "Show full ID");
export const A_HIDE_FULL_ID:       S = s('הסתר ת"ז מלאה',                 "Hide full ID");
export const A_INTEGRITY_FLAG:     S = s("דגל יושרה",                     "Integrity flag");
export const A_INJECTION_FLAG:     S = s("ניסיון הזרקת פרומפט",           "Prompt injection attempt");
export const A_EMAIL_SENT:         S = s("מייל נשלח ✓",                   "Email sent ✓");
export const A_EMAIL_NOT_SENT:     S = s("מייל טרם נשלח",                 "Email not sent yet");
export const A_EMAIL_MISSING:      S = s("חסר למייל: {fields}",           "Missing for email: {fields}");
export const A_ORAL_DEFENSE:       S = s("הגנה בעל פה",                   "Oral defense");
export const A_CODE_QUALITY:       S = s("איכות קוד",                     "Code quality");
export const A_FINAL_GRADE:        S = s("ציון סופי",                     "Final grade");
export const A_PROF_REPORT:        S = s('דו"ח למרצה',                    "Report to faculty");
export const A_FEEDBACK_ORAL:      S = s("משוב לסטודנט — בחינה בעל פה",   "Student feedback — oral exam");
export const A_FEEDBACK_STATIC:    S = s("משוב לסטודנט — קוד סטטי",       "Student feedback — static code");
export const A_TRANSCRIPT:         S = s("תמליל הבחינה",                  "Exam transcript");
export const A_GRADE_ANALYSIS:     S = s("ניתוח הציון הסופי",             "Final grade analysis");
export const A_AUTHORSHIP_NOTE:    S = s("הערת בעלות / יושרה",            "Authorship / integrity note");
export const A_CODE_REVIEW:        S = s("ביקורת קוד",                    "Code review");
export const A_EMAIL_PREVIEW:      S = s("תצוגה מקדימה — מייל ציון לסטודנט", "Preview — student grade email");
export const A_EMAIL_SUBJECT:      S = s("נושא:",                         "Subject:");

// ── Transcript rendering ──────────────────────────────────────────────────────
export const A_QUESTION_N:      S = s("שאלה {n}",                "Question {n}");
export const A_REPLACEMENT:     S = s(" (חלופית)",               " (replacement)");
export const A_TIME_UP_BADGE:   S = s("⏱ פג הזמן",               "⏱ Time up");
export const A_TIME_UP_TITLE:   S = s("הזמן נגמר על שאלה זו",    "Time ran out on this question");
export const A_DIFF_EASY:       S = s("קלה",                     "Easy");
export const A_DIFF_MEDIUM:     S = s("בינונית",                 "Medium");
export const A_DIFF_HARD:       S = s("קשה",                     "Hard");
export const A_UNDERSTANDING:   S = s("הבנה:",                   "Understanding:");
export const A_ANSWER:          S = s("תשובה",                   "Answer");
export const A_ANSWER_SWITCH:   S = s("תשובה (בקשת החלפה)",      "Answer (switch requested)");

// ── Assignment overview ───────────────────────────────────────────────────────
export const A_OVERVIEW_TITLE:  S = s("סקירת מטלה — {name}",     "Assignment overview — {name}");
export const A_N_EXAMINED:      S = s("{n} סטודנטים נבחנו",      "{n} students examined");
export const A_UPDATED_AT:      S = s("עודכן {time}",            "Updated {time}");
export const A_REFRESH:         S = s("↻ רענן",                  "↻ Refresh");
export const A_REFRESH_TITLE:   S = s("רענן נתונים",             "Refresh data");
export const A_EXPORT_CSV:      S = s("ייצוא CSV",               "Export CSV");
export const A_EXPORTING:       S = s("מייצא...",                "Exporting…");
export const A_AVERAGES:        S = s("ממוצעים",                 "Averages");
export const A_MEDIAN:          S = s("חציון {v}",               "median {v}");
export const A_N_INCOMPLETE:    S = s("{n} סטודנטים לא השלימו בזמן", "{n} students did not finish in time");
export const A_GRADE_DIST:      S = s("התפלגות ציון סופי",       "Final grade distribution");
export const A_AUTH_DIST:       S = s("התפלגות בעלות",           "Authorship distribution");
export const A_ID_STATUS_TITLE: S = s('מצב זיהוי ת"ז',           "ID resolution status");
export const A_FLAGGED:         S = s("סטודנטים מסומנים ({n})",  "Flagged students ({n})");
export const A_ALL_STUDENTS:    S = s("כל הסטודנטים",            "All students");

// Student table
export const A_COL_NAME:        S = s("שם",                      "Name");
export const A_COL_ID:          S = s('ת"ז',                     "ID");
export const A_COL_FINAL:       S = s("סופי",                    "Final");
export const A_COL_ORAL:        S = s('בע"פ',                    "Oral");
export const A_COL_CODE:        S = s("קוד",                     "Code");
export const A_COL_WHEN:        S = s("מועד",                    "When");
export const A_COL_DURATION:    S = s("זמן",                     "Time");
export const A_COL_AUTHORSHIP:  S = s("בעלות",                   "Authorship");
export const A_DURATION_TITLE:  S = s("זמן מתחילת הבחינה עד הכניסה האחרונה בתמלול",
                                      "Time from exam start to the last transcript entry");
// Badges
export const A_BADGE_TIMEOUT:   S = s("פג הזמן",                 "Timed out");
export const A_BADGE_SWITCH:    S = s("ניצל החלפת שאלה",         "Used a question switch");
export const A_BADGE_ID:        S = s("זיהוי: {status}",         "ID resolution: {status}");
export const A_BADGE_FLAG:      S = s("דגל יושרה",               "Integrity flag");

// Filters
export const A_FILTER_TIMEOUT:  S = s("⏱ חרגו בזמן",             "⏱ Timed out");
export const A_FILTER_SWITCH:   S = s("↔ ניצלו החלפה",           "↔ Used a switch");
export const A_FILTER_BAD_ID:   S = s("⚠ זיהוי בעייתי",          "⚠ ID problem");
export const A_FILTER_FLAGGED:  S = s("🚩 דגל יושרה",            "🚩 Integrity flag");
export const A_FILTER_MAX:      S = s("ציון עד",                 "Grade up to");
export const A_FILTER_CLEAR:    S = s("נקה פילטרים",             "Clear filters");
export const A_FILTER_EMPTY:    S = s("אין סטודנטים התואמים לפילטרים שנבחרו",
                                      "No students match the selected filters");

// ── Question statistics ───────────────────────────────────────────────────────
export const A_QSTATS_TITLE:    S = s("סטטיסטיקות שאלות",        "Question statistics");
export const A_N_EXAMS:         S = s("{n} בחינות",              "{n} exams");
export const A_QSTATS_EMPTY:    S = s("אין נתוני שאלות זמינים למטלה זו",
                                      "No question data available for this assignment");
export const A_QCOL_ID:         S = s("מזהה",                    "ID");
export const A_QCOL_TOPIC:      S = s("נושא",                    "Topic");
export const A_QCOL_DIFFICULTY: S = s("קושי",                    "Difficulty");
export const A_QCOL_ASKED:      S = s("נשאלה",                   "Asked");
export const A_QCOL_SWITCHED:   S = s("הוחלפה",                  "Switched");
export const A_QCOL_REASKED:    S = s("הסברה מחדש",              "Re-asked");
export const A_QCOL_AVG:        S = s("ממוצע ציון (1–5)",        "Mean score (1–5)");

// ── Item analysis ─────────────────────────────────────────────────────────────
export const A_ITEM_TITLE:      S = s("ניתוח איכות שאלות",       "Question quality analysis");
export const A_ITEM_COMPUTED:   S = s("חושב {time}",             "computed {time}");
export const A_ITEM_NO_DIV:     S = s(" · ללא מדד גיוון",        " · no divergence metric");
export const A_ITEM_PENDING:    S = s("טרם חושב — ירוץ אוטומטית ב-23:00",
                                      "Not computed yet — runs automatically at 23:00");
export const A_ITEM_NO_REPORT:  S = s("אין דוח זמין למטלה זו עדיין.",
                                      "No report available for this assignment yet.");
export const A_ITEM_NO_QS:      S = s("אין נתוני שאלות.",        "No question data.");
// Per-metric definitions for the item-analysis panel. Kept as one definition per
// metric (rather than a run-on paragraph) so each column header can be looked up
// directly. Computed in backend/scripts/item_analysis.py.
export const A_ITEM_LEGEND_TITLE: S = s("מה המדדים אומרים?", "What these metrics mean");

export const A_ITEM_DEF_TAKE: S = s(
  "אחוז הפעמים שהבוחן בחר בשאלה מתוך הפעמים שהוצעה לו. בכל תור מוצעות לבוחן 6 אפשרויות והוא בוחר אחת, ולכן כ-17% הוא הבסיס הרגיל ולא ציון נמוך. מתחת ל-5% = הבוחן כמעט תמיד מדלג עליה — שקול לשכתב או להסיר.",
  "How often the examiner picked this question out of the times it was offered. Six candidates are offered each turn and the examiner picks one, so ~17% is the normal baseline — not a poor score. Below 5% means the examiner almost always passes it over: consider rewriting or removing it.",
);
export const A_ITEM_DEF_RESIDUAL: S = s(
  "כמה טוב יותר (או פחות) ענו הנבחנים על השאלה הזו לעומת שאר השאלות שלהם עצמם, בסולם 1–5. חיובי = קלה ביחס לרמת מי שנשאל אותה; שלילי = קשה ביחס אליהם; סביב 0 = מתנהגת לפי תווית הקושי שלה. המדד מנטרל את זה שהבחירה האדפטיבית שולחת נבחנים חזקים לשאלות קשות — ולכן הוא שימושי לאיתור תוויות קושי שגויות.",
  "How much better (or worse) students scored on this question than on their own other questions, on the 1–5 scale. Positive = easy relative to the students who got it; negative = hard relative to them; near 0 = behaves as its difficulty label implies. It cancels out the fact that adaptive selection sends stronger students to harder questions, which is what makes it useful for spotting mislabelled difficulty.",
);
export const A_ITEM_DEF_CEILING: S = s(
  "אחוז הנבחנים שקיבלו 5 על השאלה. 0% על פני מספיק נבחנים = אין לשאלה תקרה, ייתכן שהיא רדודה מדי.",
  "Share of students who scored 5. A sustained 0% means the question has no headroom — it may lack depth.",
);
export const A_ITEM_DEF_DISCRIM: S = s(
  "מתאם בין הציון בשאלה לרמת הסטודנט (לפי שאר שאלותיו). חיובי = השאלה מפרידה נכון בין חזקים לחלשים; שלילי = דווקא החזקים נכשלו בה — סימן אפשרי לשאלה מבלבלת או דו-משמעית.",
  "Correlation between the score on this question and the student's overall level (from their other questions). Positive = the question separates strong from weak correctly; negative = the strong students are the ones failing it — a possible sign of a confusing or ambiguous question.",
);
export const A_ITEM_DEF_DIVERGENCE: S = s(
  "עד כמה אותה שאלה מנוסחת שונה בין סטודנטים: 🟢 טוב · 🟡 גבולי · 🔴 תבניתי (אותה שאלה עם שינויי שם, שקול להחליף).",
  "How differently the same pool entry gets phrased across students: 🟢 good · 🟡 borderline · 🔴 formulaic (the same question with names swapped — consider replacing).",
);
export const A_ITEM_DEF_NOTE: S = s(
  "עם 3 שאלות בלבד לכל נבחן, שארית והבחנה רועשות — התייחס אליהן כסימן לבדיקה ידנית, לא כהוכחה.",
  "With only 3 questions per student, residual and discrimination are noisy — treat them as a prompt for manual review, not as proof.",
);
export const A_ICOL_TAKE:       S = s("בחירה%",                  "Take %");
export const A_ICOL_RESIDUAL:   S = s("שארית",                   "Residual");
export const A_ICOL_CEILING:    S = s("תקרה%",                   "Ceiling %");
export const A_ICOL_DISCRIM:    S = s("הבחנה",                   "Discrim.");
export const A_ICOL_DIVERGENCE: S = s("גיוון",                   "Divergence");
export const A_ICOL_RECS:       S = s("המלצות",                  "Recommendations");
export const A_ITEM_OK:         S = s("תקין",                    "OK");
export const A_DISCRIM_TITLE:   S = s(
  "הבחנה — מתאם עם רמת הסטודנט. שלילי = החזקים דווקא נכשלו (רועש עם 3 שאלות)",
  "Discrimination — correlation with student level. Negative = the strong students failed it (noisy with 3 questions)",
);

// ── Participation & email status ──────────────────────────────────────────────
export const A_PARTICIPATION:     S = s("השתתפות ומצב מיילים",      "Participation & email status");
export const A_PART_LOADING:      S = s("טוען נתוני השתתפות ולוח שנה…",
                                        "Loading participation and calendar data…");
export const A_SEND_REMINDERS:    S = s("שלח תזכורות הרשמה",        "Send signup reminders");
export const A_STAT_EXAMINED:     S = s("נבחנו",                    "Examined");
export const A_STAT_EMAILED:      S = s("קיבלו מייל",               "Emailed");
export const A_STAT_NO_ROSTER:    S = s("אין רשימה",                "No roster");
export const A_STAT_PRE_SURVEY:   S = s("סקר מקדים",                "Pre-survey");
export const A_STAT_POST_SURVEY:  S = s("סקר מסכם",                 "Post-survey");
export const A_STAT_AVG_EXAM:     S = s("זמן בחינה ממוצע",          "Mean exam time");
export const A_STAT_AVG_AI:       S = s("המתנה לAI ממוצע",          "Mean AI wait");
export const A_STAT_AVG_EXAM_T:   S = s(
  "ממוצע זמן בחינה מלאה (3 שאלות) מרגע ההתחלה עד הכניסה האחרונה בתמלול",
  "Mean duration of a full 3-question exam, from start to the last transcript entry",
);
export const A_STAT_AVG_AI_T:     S = s(
  "ממוצע זמן המתנה לתגובת AI (מרגע שליחת תשובת הסטודנט ועד קבלת שאלת הבוחן הבאה)",
  "Mean wait for an AI response (from the student submitting an answer to the next examiner question)",
);
export const A_COL_EMAIL_SENT:    S = s("מייל נשלח",               "Email sent");
export const A_COL_EMAIL_READY:   S = s("מייל מוכן",               "Email ready");

// ── Reminder modal ────────────────────────────────────────────────────────────
export const A_REM_TITLE:       S = s("שליחת תזכורות הרשמה",       "Send signup reminders");
export const A_REM_SENT:        S = s("נשלח!",                     "Sent!");
export const A_REM_RESULT:      S = s("נשלחו: {sent} · נכשלו: {failed}",
                                      "Sent: {sent} · Failed: {failed}");
export const A_REM_CAL_WARN:    S = s("אזהרה — יומן: {error}",     "Warning — calendar: {error}");
export const A_REM_PENDING:     S = s("{n} סטודנטים טרם נרשמו מתוך {total} נדרשים",
                                      "{n} of {total} required students have not signed up yet");
export const A_REM_NO_EMAIL:    S = s(" · {n} ללא כתובת מייל",     " · {n} with no email address");
export const A_REM_SELECT_ALL:  S = s("בחר הכל",                   "Select all");
export const A_REM_ALL_DONE:    S = s("כל הסטודנטים הנדרשים כבר נרשמו!",
                                      "All required students have already signed up!");
export const A_REM_CAL_LINK:    S = s("קישור להרשמה ביומן",        "Calendar signup link");
export const A_REM_SUBJECT:     S = s("נושא המייל",                "Email subject");
export const A_REM_BODY:        S = s("גוף המייל",                 "Email body");
export const A_REM_BODY_HINT:   S = s("({name} ו-{calendar_link} יוחלפו אוטומטית)",
                                      "({name} and {calendar_link} are substituted automatically)");
export const A_REM_TEST:        S = s("שלח לעצמי (בדיקה)",         "Send to myself (test)");
export const A_REM_SEND_N:      S = s("שלח ל-{n} סטודנטים",        "Send to {n} students");
export const A_REM_TEST_OK:     S = s("נשלח בהצלחה אל {to}",       "Sent successfully to {to}");

// ── Language toggle ───────────────────────────────────────────────────────────
export const A_LANG_TOGGLE_TITLE: S = s("Switch to English", "עבור לעברית");
