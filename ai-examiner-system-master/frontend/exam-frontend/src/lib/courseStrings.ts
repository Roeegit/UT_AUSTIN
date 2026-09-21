/**
 * courseStrings.ts — entry-flow strings that differ between courses.
 *
 * Two axes, both decided by the backend (`GET /api/config`) because one frontend image
 * serves every course and nothing course-specific can be baked in at build time:
 *
 *   identity_mode   what a student identifies with — a GitHub Classroom course asks for a
 *                   username, a Google Form course for a university ID. Derived from
 *                   config.FORM_SOURCES, so registering a Form assignment switches the
 *                   wording too.
 *   submission_kind what they submitted — Operating Systems students submit code, Linear
 *                   Algebra students submit a written solution. Calling a proof "your
 *                   code" reads as a bug to the student.
 *
 * These screens run before language selection, so they are Hebrew-only — same as the rest
 * of the entry flow. Language variants live in uiStrings.ts / welcomeStrings.ts.
 */

export type IdentityMode = "github_username" | "university_id";
export type SubmissionKind = "code" | "solution";

type IdS = Record<IdentityMode, string>;
type SubS = Record<SubmissionKind, string>;

const id = (github: string, universityId: string): IdS => ({
  github_username: github,
  university_id: universityId,
});

const sub = (code: string, solution: string): SubS => ({ code, solution });

// ── Identity: EntryScreen ─────────────────────────────────────────────────────
export const ID_ENTRY_PROMPT: IdS = id(
  "הזן את שם המשתמש שלך ב-GitHub להתחלה",
  "הזן את מספר תעודת הזהות שלך להתחלה",
);
export const ID_FIELD_LABEL: IdS = id("שם משתמש GitHub", "מספר תעודת זהות");
export const ID_PREFILL_NOTE: IdS = id(
  "שם המשתמש שלי ב-GitHub לא מזוהה: ",
  "מספר תעודת הזהות שלי לא מזוהה: ",
);
export const ID_NOT_RECOGNISED: IdS = id(
  "שם המשתמש שלי לא מזוהה — פנייה לסגל",
  "מספר תעודת הזהות שלי לא מזוהה — פנייה לסגל",
);

// ── Identity: RosterConfirmScreen ─────────────────────────────────────────────
export const ID_CONFIRM_LABEL: IdS = id("GitHub:", "ת.ז.:");
export const ID_WRONG_IDENTIFIER: IdS = id(
  "שם המשתמש ב-GitHub שגוי",
  "מספר תעודת הזהות שגוי",
);
export const ID_NO_FILES: IdS = id(
  "לא נמצאו קבצים עבור משתמש GitHub זה.",
  "לא נמצאו קבצים עבור מספר תעודת זהות זה.",
);

// ── Submission kind: RosterConfirmScreen ──────────────────────────────────────
export const SUB_CONFIRM_TITLE: SubS = sub("האם זה הקוד שלך?", "האם זו ההגשה שלך?");
export const SUB_CONFIRM_SUBTITLE: SubS = sub(
  "בדוק שהקוד שמוצג משמאל הוא הקוד שהגשת.",
  "בדוק שההגשה שמוצגת משמאל היא זו שהגשת.",
);
export const SUB_CONFIRM_BTN: SubS = sub(
  "כן, זה הקוד שלי — המשך",
  "כן, זו ההגשה שלי — המשך",
);
export const SUB_LOAD_ERROR: SubS = sub(
  "לא ניתן לטעון את הקוד כרגע.",
  "לא ניתן לטעון את ההגשה כרגע.",
);
export const SUB_NETWORK_ERROR: SubS = sub(
  "שגיאת רשת בטעינת הקוד.",
  "שגיאת רשת בטעינת ההגשה.",
);
export const SUB_PROBLEM_NOTE: SubS = sub(
  "אם שם המטלה שגוי, הקוד אינו שלך, או שיש בעיה אחרת — פנה אלינו.",
  "אם שם המטלה שגוי, ההגשה אינה שלך, או שיש בעיה אחרת — פנה אלינו.",
);

// ── Helpers ───────────────────────────────────────────────────────────────────
export function ti(strings: IdS, mode: IdentityMode): string {
  return strings[mode] ?? strings.github_username;
}

export function ts(strings: SubS, kind: SubmissionKind): string {
  return strings[kind] ?? strings.code;
}
