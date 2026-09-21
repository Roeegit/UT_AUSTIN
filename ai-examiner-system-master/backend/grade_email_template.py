"""
grade_email_template.py — Hebrew grade email sent to students after grading.

Usage:
  subject, body = build_grade_email(blob_data)

`blob_data` is the parsed JSON from the GCS results blob.
"""

# ── Configuration ────────────────────────────────────────────────────────────

# Flat bonus added to finalWeightedGrade for all students this semester.
# TODO: confirm this value is correct before sending (Shachar, 2026-05-11)
ADAPTATION_BONUS_POINTS = 10

POST_SURVEY_URL = "https://docs.google.com/forms/d/e/1FAIpQLScgjuaK3HC1QObG2BTR8ga4ROyTNz8KCTdywfcL9zGcMfgYPg/viewform"

_ASSIGNMENT_LABELS_HE: dict[str, str] = {
    "biu-os-2026-assignment-1-claude-code-shell-hooks": "מטלה 1 — Claude Code Shell Hooks",
    "assignment-2": "מטלה 2",
    "assignment-3": "מטלה 3",
}


# ── Public API ───────────────────────────────────────────────────────────────

def validate_email_readiness(blob: dict) -> dict:
    """
    Check whether a result blob has all fields required to send a grade email.
    Returns {"is_valid": bool, "missing_fields": [str]}.
    """
    missing = []
    gv = blob.get("grader_verdict") or {}
    cr = blob.get("code_review") or {}
    fg = blob.get("final_grade") or {}

    if not (gv.get("studentFeedback") or "").strip():
        missing.append("studentFeedback")
    if not (cr.get("studentStaticFeedback") or "").strip():
        missing.append("studentStaticFeedback")
    if not (blob.get("hebrew_name") or "").strip():
        missing.append("hebrew_name")
    if not isinstance(fg.get("oralDefenseScore"), (int, float)):
        missing.append("oralDefenseScore")
    if not isinstance(fg.get("staticCodeQualityScore"), (int, float)):
        missing.append("staticCodeQualityScore")
    if not isinstance(fg.get("finalWeightedGrade"), (int, float)):
        missing.append("finalWeightedGrade")

    return {"is_valid": len(missing) == 0, "missing_fields": missing}


def build_grade_email(blob: dict, extra_bonus: int = 0, connection_bonus: int = 0) -> tuple[str, str]:
    """
    Build (subject, body) for the student grade email.
    `blob` is the parsed GCS result JSON for the student.

    `extra_bonus` is a per-student assignment bonus (e.g. the optional REPORT.md
    bonus, up to +5) added on top of the weighted grade and the adaptation bonus,
    with the total capped at 100. Pass 0 (default) for students with no bonus.

    `connection_bonus` is a per-student make-good for a technical disruption during
    the exam (e.g. a brief disconnection). Added after the other bonuses, capped at
    100, and shown as its own labeled line. Pass 0 (default) when there is none.
    """
    assignment_name = blob.get("assignment_name", "")
    assignment_label = _ASSIGNMENT_LABELS_HE.get(assignment_name, assignment_name)

    name    = blob.get("hebrew_name") or blob.get("github_username", "סטודנט")
    grade   = blob.get("final_grade", {})
    oral    = grade.get("oralDefenseScore")
    static  = grade.get("staticCodeQualityScore")
    base    = grade.get("finalWeightedGrade")

    try:
        extra_bonus = int(extra_bonus or 0)
    except (TypeError, ValueError):
        extra_bonus = 0
    try:
        connection_bonus = int(connection_bonus or 0)
    except (TypeError, ValueError):
        connection_bonus = 0

    # Compute displayed final grade. Bonuses stack on the weighted base, each step
    # capped at 100:
    #   • adaptation bonus (+10) — everyone examined via the system
    #   • assignment bonus (extra_bonus) — per-student, e.g. REPORT.md (0 if none)
    #   • connection bonus — per-student make-good for a technical disruption (0 if none)
    if isinstance(base, (int, float)):
        after_adapt  = min(100, round(base + ADAPTATION_BONUS_POINTS))
        after_report = min(100, after_adapt + extra_bonus)
        final        = min(100, after_report + connection_bonus)
    else:
        final = "—"
        base  = "—"
        after_adapt = "—"
        after_report = "—"
        oral  = oral if oral is not None else "—"
        static = static if static is not None else "—"

    # Optional REPORT.md bonus line — shown only when the student earned a bonus.
    if extra_bonus > 0 and isinstance(after_adapt, int):
        report_line = (
            "שלב 4 — בונוס דוח (REPORT.md):\n"
            f"  {after_adapt} + {extra_bonus} = {after_report}/100\n"
        )
    else:
        report_line = ""

    # Optional connection-error bonus line — make-good for a technical disruption.
    # Step number follows the report-bonus step so there's no gap (4 if no report
    # bonus, 5 if there is one).
    if connection_bonus > 0 and isinstance(after_report, int):
        connection_step = 5 if extra_bonus > 0 else 4
        connection_line = (
            f"שלב {connection_step} — בונוס תקלת תקשורת (ניתוק זמני במהלך הבחינה):\n"
            f"  {after_report} + {connection_bonus} = {final}/100\n"
        )
    else:
        connection_line = ""

    # Student-facing oral exam feedback (from grader LLM, in Hebrew)
    grader_verdict  = blob.get("grader_verdict") or {}
    student_feedback = grader_verdict.get("studentFeedback", "")

    # Student-facing static code feedback (from code reviewer LLM, in Hebrew)
    code_review = blob.get("code_review") or {}
    student_static_feedback = code_review.get("studentStaticFeedback", "")

    subject = f"ציון הערכת ידע — {assignment_label}"

    body = f"""\
שלום {name},

הערכת הידע האוטומטית על {assignment_label} הסתיימה, והציון שלך מוכן.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
פירוט הציון
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

שלב 1 — ציון הגנה בעל-פה (75% מהציון):
  ציון:  {oral}/100

שלב 2 — ציון איכות הקוד (25% מהציון):
  ציון:  {static}/100

חישוב ציון ממוצע משוקלל:
  (0.75 × {oral}) + (0.25 × {static}) = {base}/100
שלב 3 — בונוס הסתגלות למערכת החדשה (+{ADAPTATION_BONUS_POINTS} נקודות לכלל הנבדקים באמצעות המערכת)
  {base} + {ADAPTATION_BONUS_POINTS} = {after_adapt}/100
{report_line}{connection_line}
► ציון סופי: {final}/100

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
משוב על ההגנה בעל-פה
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{student_feedback if student_feedback else "אין משוב נוסף."}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
משוב על איכות הקוד
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{student_static_feedback if student_static_feedback else "אין משוב נוסף."}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
סקר
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

לאחר קבלת הציון, יש למלא את סקר ה-AI (חובה):
{POST_SURVEY_URL}

מילוי הסקר הוא חלק מדרישות הקורס.

אנו רואים חשיבות עליונה בלמידה ותרגול רציפים, ולכן במידה ואינך מרוצה מהציון באפשרותך לקבוע מועד למבחן חוזר באמצעות המערכת.  כדי לתאם זאת, יש לפנות לסגל הקורס.
בברכה,
צוות הקורס — מערכות הפעלה, אוניברסיטת בר-אילן

---
זהו מייל אוטומטי אין להשיב למייל זה.
"""

    return subject, body


def build_grade_email_html(plain_body: str) -> str:
    """
    Wrap a plain-text grade email body in an RTL HTML shell so Hebrew
    renders correctly in all email clients.
    """
    import html
    escaped = html.escape(plain_body)
    return f"""\
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body {{
    font-family: Arial, sans-serif;
    direction: rtl;
    text-align: right;
    color: #222;
    max-width: 600px;
    margin: 0 auto;
    padding: 20px;
    font-size: 14px;
    line-height: 1.7;
    background: #fff;
  }}
  pre {{
    font-family: Arial, sans-serif;
    white-space: pre-wrap;
    word-break: break-word;
    direction: rtl;
    text-align: right;
    margin: 0;
  }}
</style>
</head>
<body><pre>{escaped}</pre></body>
</html>"""
