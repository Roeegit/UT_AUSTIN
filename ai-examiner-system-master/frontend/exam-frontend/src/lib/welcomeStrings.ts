/**
 * welcomeStrings.ts — All WelcomeScreen text constants.
 * Edit this file to update the briefing text without touching component logic.
 *
 * Each key contains four variants: male_he, female_he, male_en, female_en.
 */

export type Gender   = "male" | "female";
export type Language = "he" | "en";

interface StringVariants {
  male_he:   string;
  female_he: string;
  male_en:   string;
  female_en: string;
}

function pick(v: StringVariants, gender: Gender, lang: Language): string {
  return v[`${gender}_${lang}` as keyof StringVariants];
}

// ── Page title / subtitle ─────────────────────────────────────────────────────

export const WELCOME_TITLE: StringVariants = {
  male_he:   'ברוך הבא להערכת ידע ב"{assignment}" בקורס מערכות הפעלה',
  female_he: 'ברוכה הבאה להערכת ידע ב"{assignment}" בקורס מערכות הפעלה',
  male_en:   'Welcome to the "{assignment}" Knowledge Assessment — Operating Systems',
  female_en: 'Welcome to the "{assignment}" Knowledge Assessment — Operating Systems',
};

export const WELCOME_TITLE_BARE: StringVariants = {
  male_he:   'ברוך הבא להערכת ידע בקורס מערכות הפעלה',
  female_he: 'ברוכה הבאה להערכת ידע בקורס מערכות הפעלה',
  male_en:   'Welcome to the Knowledge Assessment — Operating Systems',
  female_en: 'Welcome to the Knowledge Assessment — Operating Systems',
};

export const WELCOME_SUBTITLE: StringVariants = {
  male_he:   "כמה מילים לפני שמתחילים",
  female_he: "כמה מילים לפני שמתחילים",
  male_en:   "A few words before we begin",
  female_en: "A few words before we begin",
};

// ── Explanation bullets ───────────────────────────────────────────────────────

export const BULLET_AI: StringVariants = {
  male_he: (
    "עוד מעט תתחיל הערכת ידע בעל-פה אוטומטית. " +
    "<strong>בוחן מבוסס בינה מלאכותית</strong> ישאל אותך שאלות על הקוד שהגשת במטלה שלך — " +
    "בדיוק כפי שמרצה היה עושה."
  ),
  female_he: (
    "עוד מעט תתחיל הערכת ידע בעל-פה אוטומטית. " +
    "<strong>בוחן מבוסס בינה מלאכותית</strong> ישאל אותך שאלות על הקוד שהגשת במטלה שלך — " +
    "בדיוק כפי שמרצה היה עושה."
  ),
  male_en: (
    "In a moment, an automated oral knowledge assessment will begin. " +
    "An <strong>AI-powered evaluator</strong> will ask you questions about the code you submitted — " +
    "exactly as a lecturer would."
  ),
  female_en: (
    "In a moment, an automated oral knowledge assessment will begin. " +
    "An <strong>AI-powered evaluator</strong> will ask you questions about the code you submitted — " +
    "exactly as a lecturer would."
  ),
};

export const BULLET_LAYOUT: StringVariants = {
  male_he: (
    "<strong>בצד שמאל</strong> תראה את הקוד שלך. " +
    "<strong>בצד ימין</strong> תופיע השאלה ותיבת המענה שלך. " +
    "לפעמים הבוחן יפנה אותך לשורה מסוימת בקוד — היא תהיה מודגשת בצד שמאל."
  ),
  female_he: (
    "<strong>בצד שמאל</strong> תראי את הקוד שלך. " +
    "<strong>בצד ימין</strong> תופיע השאלה ותיבת המענה שלך. " +
    "לפעמים הבוחן יפנה אותך לשורה מסוימת בקוד — היא תהיה מודגשת בצד שמאל."
  ),
  male_en: (
    "<strong>On the left</strong> you will see your code. " +
    "<strong>On the right</strong> the question and your answer box will appear. " +
    "Sometimes the examiner will point you to a specific line of code — it will be highlighted on the left."
  ),
  female_en: (
    "<strong>On the left</strong> you will see your code. " +
    "<strong>On the right</strong> the question and your answer box will appear. " +
    "Sometimes the examiner will point you to a specific line of code — it will be highlighted on the left."
  ),
};

export const BULLET_ANSWER: StringVariants = {
  male_he: (
    "<strong>הקלד את תשובתך</strong> — הסבר את הגישה שלך, את החשיבה שלך, ומה הקוד שלך עושה. " +
    "אין צורך בתשובות מושלמות — נסח את דבריך בטבעיות ובישירות כמו שאתה מסביר לחבר."
  ),
  female_he: (
    "<strong>הקלידי את תשובתך</strong> — הסברי את הגישה שלך, את החשיבה שלך, ומה הקוד שלך עושה. " +
    "אין צורך בתשובות מושלמות — נסחי את דברייך בטבעיות ובישירות כמו שאת מסבירה לחבר."
  ),
  male_en: (
    "<strong>Type your answer</strong> — explain your approach, your reasoning, and what your code does. " +
    "Answers don't need to be perfect — express yourself naturally, as if explaining to a friend."
  ),
  female_en: (
    "<strong>Type your answer</strong> — explain your approach, your reasoning, and what your code does. " +
    "Answers don't need to be perfect — express yourself naturally, as if explaining to a friend."
  ),
};

export const BULLET_TIMER: StringVariants = {
  male_he:   "יש לך <strong>{minutes} דקות</strong> לכלל ההערכה, כולל כדקה של המתנה ל-3 השאלות. נהל את הזמן שלך.",
  female_he: "יש לך <strong>{minutes} דקות</strong> לכלל ההערכה, כולל כדקה של המתנה ל-3 השאלות. נהלי את הזמן שלך.",
  male_en:   "You have <strong>{minutes} minutes</strong> for the entire assessment, including about a minute of wait time for the 3 questions. Manage your time wisely.",
  female_en: "You have <strong>{minutes} minutes</strong> for the entire assessment, including about a minute of wait time for the 3 questions. Manage your time wisely.",
};

export const BULLET_NO_BACK: StringVariants = {
  male_he: (
    "<strong>לאחר שליחת תשובה אין דרך חזרה.</strong> " +
    "ודא שסיימת להקליד את תשובתך לפני שתלחץ על 'שלח'."
  ),
  female_he: (
    "<strong>לאחר שליחת תשובה אין דרך חזרה.</strong> " +
    "ודאי שסיימת להקליד את תשובתך לפני שתלחצי על 'שלח'."
  ),
  male_en: (
    "<strong>Once an answer is submitted, there is no going back.</strong> " +
    "Make sure you are satisfied with your answer before clicking 'Send'."
  ),
  female_en: (
    "<strong>Once an answer is submitted, there is no going back.</strong> " +
    "Make sure you are satisfied with your answer before clicking 'Send'."
  ),
};

export const BULLET_SWITCH: StringVariants = {
  male_he: (
    "מותר לך לבקש להחליף שאלה אחת בלבד — אם תבקש בנימוס. " +
    "שים לב: אם נאלצת לדלג על שאלה שלא ידעת לענות עליה, הדבר עשוי להשתקף בציון הסופי."
  ),
  female_he: (
    "מותר לך לבקש להחליף שאלה אחת בלבד — אם תבקשי בנימוס. " +
    "שימי לב: אם נאלצת לדלג על שאלה שלא ידעת לענות עליה, הדבר עשוי להשתקף בציון הסופי."
  ),
  male_en: (
    "You are allowed to request one question swap — if you ask politely. " +
    "Note: if you skip a question you could not answer, this may be reflected in your final grade."
  ),
  female_en: (
    "You are allowed to request one question swap — if you ask politely. " +
    "Note: if you skip a question you could not answer, this may be reflected in your final grade."
  ),
};

export const BULLET_NO_CHAT: StringVariants = {
  male_he: (
    "<strong>זו אינה שיחה.</strong> " +
    "כל קלט שאינו תשובה ישירה לשאלה — כגון בקשות עצה, שאלות נגד או שיחת חולין — " +
    "ייחשב כאי-מענה ויגרור מעבר לשאלה הבאה."
  ),
  female_he: (
    "<strong>זו אינה שיחה.</strong> " +
    "כל קלט שאינו תשובה ישירה לשאלה — כגון בקשות עצה, שאלות נגד או שיחת חולין — " +
    "ייחשב כאי-מענה ויגרור מעבר לשאלה הבאה."
  ),
  male_en: (
    "<strong>This is not a chat.</strong> " +
    "Any input that is not a direct answer to the question — such as requests for hints, " +
    "counter-questions, or off-topic text — will be treated as non-response and move on to the next question."
  ),
  female_en: (
    "<strong>This is not a chat.</strong> " +
    "Any input that is not a direct answer to the question — such as requests for hints, " +
    "counter-questions, or off-topic text — will be treated as non-response and move on to the next question."
  ),
};

export const BULLET_RELAX: StringVariants = {
  male_he: (
    "נשום עמוק — זה בסדר להיות קצת לחוץ. ההערכה נועדה לבדוק <strong>את ההבנה שלך</strong>, " +
    "לא את יכולת השינון שלך. הסבר את הקוד שלך במילים שלך."
  ),
  female_he: (
    "נשמי עמוק — זה בסדר להיות קצת לחוצה. ההערכה נועדה לבדוק <strong>את ההבנה שלך</strong>, " +
    "לא את יכולת השינון שלך. הסברי את הקוד שלך במילים שלך."
  ),
  male_en: (
    "Take a deep breath — it's okay to be a little nervous. The assessment is designed to test " +
    "<strong>your understanding</strong>, not your memorisation. Explain your code in your own words."
  ),
  female_en: (
    "Take a deep breath — it's okay to be a little nervous. The assessment is designed to test " +
    "<strong>your understanding</strong>, not your memorisation. Explain your code in your own words."
  ),
};

// ── Footer ────────────────────────────────────────────────────────────────────

export const FOOTER_GOOD_LUCK: StringVariants = {
  male_he:   "מאחלים לך הרבה בהצלחה! 🌟",
  female_he: "מאחלים לך הרבה בהצלחה! 🌟",
  male_en:   "Wishing you the best of luck! 🌟",
  female_en: "Wishing you the best of luck! 🌟",
};

export const FOOTER_START_BTN: StringVariants = {
  male_he:   "אני מוכן — נתחיל",
  female_he: "אני מוכנה — נתחיל",
  male_en:   "I'm ready — let's begin",
  female_en: "I'm ready — let's begin",
};

// ── Helper export ─────────────────────────────────────────────────────────────

export { pick };