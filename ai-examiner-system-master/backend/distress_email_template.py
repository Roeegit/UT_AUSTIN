"""
distress_email_template.py — TA notification template for the END_EXAM_DISTRESS flow.

Kept in a separate file so the message can be edited without touching dispatch logic.
"""

DISTRESS_EMAIL_SUBJECT = "[OS Exam] Student distress signal — session {session_id}"

DISTRESS_EMAIL_BODY = """\
A student distress signal was detected during an oral exam session.
The exam was ended automatically by the system.

--- Student Details ---
GitHub username: {github_username}
Assignment:      {assignment_name}

--- Session Details ---
Session ID:      {session_id}
Timestamp (UTC): {timestamp}

--- Trigger ---
The student was on question {question_number} when the distress signal was detected.

Their exact message that triggered the signal:
\"\"\"{trigger_message}\"\"\"

--- Transcript ---
Full session transcript (including all questions and answers):
  GET /api/admin/results/{github_username}

--- Next Steps ---
Session was ended automatically. The student has been informed that the TA will contact them.
Please reach out to arrange a retake or alternative arrangement.
"""
