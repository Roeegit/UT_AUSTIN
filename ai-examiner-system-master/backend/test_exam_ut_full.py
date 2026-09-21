import os
import json
import anthropic
from dotenv import load_dotenv

from plan_assembler import QuestionPicker, load_pool
from agents import call_examiner_q1, call_examiner_qn, call_grader

load_dotenv()

# Absolute paths
failed_path = r"C:\Users\הניה\Desktop\ai_examiner\submissions\Rohithk01\failed.java"
accepted_path = r"C:\Users\הניה\Desktop\ai_examiner\submissions\Rohithk01\accepted.java"
readme_path = os.path.join(os.path.dirname(__file__), "assignments", "austin-a_readme.md")
pool_path = os.path.join(os.path.dirname(__file__), "assignments", "austin-a_question_pool.json")
examiner_prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "examiner_prompt_ut.txt")
grader_prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "grader_prompt_ut.txt")

with open(failed_path, "r", encoding="utf-8", errors="replace") as f:
    failed_code = f.read()
with open(accepted_path, "r", encoding="utf-8", errors="replace") as f:
    accepted_code = f.read()
with open(readme_path, "r", encoding="utf-8") as f:
    readme = f.read()
with open(examiner_prompt_path, "r", encoding="utf-8") as f:
    examiner_prompt = f.read()
with open(grader_prompt_path, "r", encoding="utf-8") as f:
    grader_prompt = f.read()

student_files = {"failed.java": failed_code, "accepted.java": accepted_code}
full_context = f"[PROBLEM DESCRIPTION]\n{readme}\n\n[STUDENT SUBMITTED FILES]\n"
for name, content in student_files.items():
    full_context += f"\n--- File: {name} ---\n{content}\n"

pool = load_pool(pool_path)
picker = QuestionPicker(pool, seed=42, silent=True)

api_key = os.environ.get("ANTHROPIC_API_KEY")
workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
client = anthropic.Anthropic(api_key=api_key, default_headers=headers)

print(">>> Executing Turn 1...")
q1_options = picker.peek_options(["medium", "medium"])
examiner_messages, tool_id, q1_json, _ = call_examiner_q1(
    client=client,
    system_prompt=examiner_prompt,
    full_context=full_context,
    q1_options=q1_options,
    picker=picker,
    temperature=0.2,
)

# Mark chosen Q1 topic as used
chosen_q1 = next((o for o in q1_options if o and o.get("id") == q1_json.get("chosenTopicLabel")), q1_options[0])
if chosen_q1:
    picker.mark_used(chosen_q1)

transcript = [{
    "role": "Examiner",
    "content": q1_json,
}]
print("Actual keys returned in Q1:", list(q1_json.keys()))
print("Q1 payload:\n", json.dumps(q1_json, indent=2))
print(f"Q1: {q1_json['questionText']}\n")

print(">>> Executing Turn 2...")
student_ans_1 = (
    "In failed.java, the subtracted expression is the closed-form formula for the sum of squares up to n, "
    "which equals 6*f(n). Instead of subtracting the single term 6*n^2 for that step, I subtracted the cumulative "
    "sum, which caused fn to become negative almost immediately."
)
print(f"Student 1: {student_ans_1}\n")
transcript.append({"role": "Student", "content": student_ans_1})

q2_options = picker.peek_options(["easy", "easy", "medium", "medium", "hard", "hard"])
examiner_messages, tool_id, q2_json, _ = call_examiner_qn(
    client=client,
    system_prompt=examiner_prompt,
    examiner_messages=examiner_messages,
    pending_tool_use_id=tool_id,
    student_answer=student_ans_1,
    topic_options=q2_options,
    turn=2,
    picker=picker,
    temperature=0.2,
)

chosen_q2 = next((o for o in q2_options if o and o.get("id") == q2_json.get("chosenTopicLabel")), q2_options[0])
if chosen_q2:
    picker.mark_used(chosen_q2)

transcript.append({"role": "Examiner", "content": q2_json})
print(f"Q2: {q2_json['questionText']}\n")


print(">>> Executing Turn 3...")
student_ans_2 = (
    "The constant 1512307 is an upper bound. Since the max value of k is around 10^18, and f(n) grows cubically "
    "(approximately n^3 / 3), n will be around the cube root of 3 * 10^18, which is roughly 1.5 million. If I had "
    "used Long.MAX_VALUE, calculating the cubic function in the binary search would overflow the 64-bit integer limit."
)
print(f"Student 2: {student_ans_2}\n")
transcript.append({"role": "Student", "content": student_ans_2})

q3_options = picker.peek_options(["easy", "easy", "medium", "medium", "hard", "hard"])
examiner_messages, tool_id, q3_json, _ = call_examiner_qn(
    client=client,
    system_prompt=examiner_prompt,
    examiner_messages=examiner_messages,
    pending_tool_use_id=tool_id,
    student_answer=student_ans_2,
    topic_options=q3_options,
    turn=3,
    picker=picker,
    temperature=0.2,
)

chosen_q3 = next((o for o in q3_options if o and o.get("id") == q3_json.get("chosenTopicLabel")), q3_options[0])
if chosen_q3:
    picker.mark_used(chosen_q3)

transcript.append({"role": "Examiner", "content": q3_json})
print(f"Q3: {q3_json['questionText']}\n")

print(">>> Finishing Exam (Turn 4)...")
student_ans_3 = (
    "If no solution exists, the binary search interval lo <= hi becomes invalid, the loop breaks, "
    "and the function correctly returns -1 as requested by the problem description. In the failed approach, "
    "the loop condition failed to account for this and returned n anyway."
)
print(f"Student 3: {student_ans_3}\n")
transcript.append({"role": "Student", "content": student_ans_3})

q4_options = picker.peek_options(["easy", "easy", "medium", "medium", "hard", "hard"])
_, _, finish_json, _ = call_examiner_qn(
    client=client,
    system_prompt=examiner_prompt,
    examiner_messages=examiner_messages,
    pending_tool_use_id=tool_id,
    student_answer=student_ans_3,
    topic_options=q4_options,
    turn=4,
    picker=picker,
    temperature=0.2,
)

print(f"Final Action: {finish_json['action']}\n")

print(">>> Running Grader Agent...")
mock_signal_b = {"level": "none", "markersFound": 0, "analysis": "Competitive programming submission delta."}

grader_json, grader_model = call_grader(
    client=client,
    system_prompt=grader_prompt,
    assignment_readme=readme,
    signal_b=mock_signal_b,
    transcript=transcript,
)

print("\n================ FINAL GRADER VERDICT ================")
print(f"Model used: {grader_model}")
print(f"Oral Defense Score: {grader_json.get('oralDefenseScore')}/100")
print(f"Authorship Assessment: {grader_json.get('authorshipAssessment')}")
print(f"\nStudent Feedback:\n{grader_json.get('studentFeedback')}")
print(f"\nProfessor Report:\n{grader_json.get('professorReport')}")
print(f"\nScratchpad:\n{json.dumps(grader_json.get('grading_scratchpad'), indent=2)}")