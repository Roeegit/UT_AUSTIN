/**
 * uiStrings.ts — UI string constants for all screens shown after language selection.
 * Edit this file to update labels/messages without touching component logic.
 *
 * Most UI strings don't have gender variants — use Language only.
 */

import type { Language } from "./welcomeStrings";

type S = Record<Language, string>;

const s = (he: string, en: string): S => ({ he, en });

// ── Generic ───────────────────────────────────────────────────────────────────
export const UI_LOADING_EXAM:       S = s("טוען שאלות…",           "Loading questions…");
export const UI_ERROR_TITLE:        S = s("שגיאה",                "Error");
export const UI_BACK_TO_ENTRY:      S = s("חזרה למסך הכניסה",     "Back to start");

// ── QuestionDisplay ───────────────────────────────────────────────────────────
export const UI_QUESTION_LABEL:     S = s("שאלה {n} מתוך 3",      "Question {n} of 3");

// ── AnswerInput ───────────────────────────────────────────────────────────────
export const UI_ANSWER_PLACEHOLDER: S = s("כתוב את תשובתך כאן…",  "Write your answer here…");
export const UI_SUBMIT_BUTTON:      S = s("שלח תשובה",             "Submit");
export const UI_SUBMITTING:         S = s("שולח…",                 "Sending…");

// ── ExamPanel ─────────────────────────────────────────────────────────────────
export const UI_REPORT_PROBLEM:     S = s("דווח על בעיה",          "Report a problem");
export const UI_TIME_WARNING:       S = s("נותרו פחות מ-3 דקות — הגש את תשובתך בקרוב.", "Less than 3 minutes left — submit your answer soon.");

// ── NotMyCodeModal ────────────────────────────────────────────────────────────
export const UI_MODAL_TITLE:        S = s("הקוד שמוצג אינו שלי",  "The displayed code is not mine");
export const UI_MODAL_CONFIRM_Q:    S = s(
  "האם אתה בטוח שברצונך להגיש תלונה?",
  "Are you sure you want to submit a complaint?"
);
export const UI_MODAL_WARNING:      S = s(
  "לחיצה על ״אישור״ תסיים את ההערכה הנוכחית ותרשום את פנייתך. הצוות האקדמי יבדוק את הנושא ויצור עמך קשר — ייתכן שניתן יהיה לקיים את ההערכה במועד אחר.",
  "Clicking \"Confirm\" will end the current assessment and record your complaint. The academic team will review it and contact you — you may be able to retake the assessment at a later date."
);
export const UI_MODAL_CONFIRM_BTN:  S = s("אישור — הגש תלונה",    "Confirm — Submit Complaint");
export const UI_MODAL_CANCEL:       S = s("ביטול — חזרה",  "Cancel — Back");
export const UI_MODAL_CONTACT_TITLE:S = s("פרטי קשר",             "Contact Details");
export const UI_MODAL_CONTACT_SUB:  S = s(
  "השאר פרטים ליצירת קשר כדי שנוכל לעדכן אותך.",
  "Leave your contact details so we can follow up with you."
);
export const UI_MODAL_FULL_NAME:    S = s("שם מלא *",              "Full Name *");
export const UI_MODAL_PHONE_EMAIL:  S = s("אימייל *",      "Email *");
export const UI_MODAL_NOTE:         S = s("הערה נוספת (אופציונלי)","Additional Note (optional)");
export const UI_MODAL_NOTE_PH:      S = s(
  "פרט בקצרה מדוע הקוד אינו שלך…",
  "Briefly describe why this is not your code…"
);
export const UI_MODAL_SEND:         S = s("שלח תלונה",             "Send Complaint");
export const UI_MODAL_BACK:         S = s("חזרה",                  "Back");
export const UI_MODAL_SENDING:      S = s("שולח תלונה…",           "Sending complaint…");
export const UI_MODAL_SUCCESS:      S = s("התלונה נרשמה בהצלחה",  "Complaint recorded successfully");
export const UI_MODAL_REDIRECT:     S = s("מועבר לסיכום…",         "Redirecting to summary…");
export const UI_MODAL_ERROR_TITLE:  S = s("שגיאה בהגשת התלונה",   "Error submitting complaint");
export const UI_MODAL_RETRY:        S = s("נסה שוב",               "Try Again");

// ── CompletedScreen ───────────────────────────────────────────────────────────
export const UI_DONE_TITLE:         S = s("ההערכה הסתיימה",        "Assessment Complete");
export const UI_DONE_BODY:          S = s(
  "תשובותיך נקלטו ויוערכו בקרוב.",
  "Your answers have been recorded and will be evaluated shortly."
);
export const UI_TIMEOUT_MSG:        S = s("זמננו תם.",              "Time's up.");
export const UI_VIEW_RESULTS:       S = s("צפה בתוצאות ←",         "View Results →");
export const UI_DONE_BTN:           S = s("סיום",                   "Done");

export const UI_COMPLAINT_DONE_TITLE: S = s("התלונה נרשמה",        "Complaint Recorded");
export const UI_COMPLAINT_DONE_BODY:  S = s(
  "פנייתך התקבלה ותיבדק על-ידי הצוות האקדמי.\nאנו ניצור עמך קשר בהקדם האפשרי.",
  "Your complaint has been received and will be reviewed by the academic team.\nWe will contact you as soon as possible."
);
export const UI_COMPLAINT_DONE_NOTE: S = s("ניתן לעזוב את החדר.", "You may leave the room.");
export const UI_CLOSE_DOOR:          S = s("אנא סגור את הדלת בצאתך.", "Please close the door when you leave.");

export const UI_DISTRESS_BODY:       S = s(
  "צוות הקורס יצור איתך קשר בקרוב.",
  "The course team will contact you shortly."
);

// ── Helper ────────────────────────────────────────────────────────────────────
export function t(strings: S, lang: Language): string {
  return strings[lang] ?? strings.he;
}
