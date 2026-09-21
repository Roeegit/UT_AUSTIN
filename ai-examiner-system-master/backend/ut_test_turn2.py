import os
import json
import anthropic
from dotenv import load_dotenv

from plan_assembler import QuestionPicker, load_pool
from agents import call_examiner_q1, call_examiner_qn

load_dotenv()

# Absolute paths
failed_path = r"C:\Users\הניה\Desktop\ai_examiner\submissions\Rohithk01\failed.java"
accepted_path = r"C:\Users\הניה\Desktop\ai_examiner\submissions\Rohithk01\accepted.java"
readme_path = os.path.join(os.path.dirname(__file__), "assignments", "austin-a_readme.md")
pool_path = os.path.join(os.path.dirname(__file__), "assignments", "austin-a_question_pool.json")
prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "examiner_prompt_ut.txt")

with open(failed_path, "r", encoding="utf-8", errors="replace") as f:
    failed_code = f.read()

with open(accepted_path, "r", encoding="utf-8", errors="replace") as f:
    accepted_code = f.read()

with open(readme_path, "r", encoding="utf-8") as f:
    readme = f.read()

with open(prompt_path, "r", encoding="utf-8") as f:
    system_prompt = f.read()

student_files = {
    "failed.java": failed_code,
    "accepted.java": accepted_code,
}

full_context = f"[PROBLEM DESCRIPTION]\n{readme}\n\n[STUDENT SUBMITTED FILES]\n"
for name, content in student_files.items():
    full_context += f"\n--- File: {name} ---\n{content}\n"

# 1. Setup Picker & Run Turn 1
pool = load_pool(pool_path)
picker = QuestionPicker(pool, seed=42, silent=True)
q1_options = picker.peek_options(["medium", "medium"])

api_key = os.environ.get("ANTHROPIC_API_KEY")
workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
client = anthropic.Anthropic(api_key=api_key, default_headers=headers)

print("Running Turn 1...")
examiner_messages, tool_use_id, q1_json, _ = call_examiner_q1(
    client=client,
    system_prompt=system_prompt,
    full_context=full_context,
    q1_options=q1_options,
    picker=picker,
    temperature=0.2,
)

# Mark chosen Q1 topic as used
chosen_q1 = next((o for o in q1_options if o and o.get("id") == q1_json.get("chosenTopicLabel")), q1_options[0])
if chosen_q1:
    picker.mark_used(chosen_q1)

print(f"Q1 asked: {q1_json.get('questionText')[:90]}...")

# 2. Simulate Student Answer to Q1
# (A strong answer explaining the formula error)
simulated_student_answer = (
    "In failed.java, the expression ((n*n) + n)*((2*n) + 1) is equal to 2n^3 + 3n^2 + n, "
    "which is 6 * f(n), the sum of all squares from 1 to n. Instead of subtracting just the incremental "
    "term for step n (which would be 6 * n^2), my while loop was repeatedly subtracting the entire prefix sum. "
    "Because of this, fn decreased way too fast and quickly became negative, so it never properly matched "
    "the condition and returned an incorrect n."
)

print(f"\nSimulated Student Answer:\n\"{simulated_student_answer}\"")

# 3. Peek Q2 options (2 easy, 2 medium, 2 hard)
q2_options = picker.peek_options(["easy", "easy", "medium", "medium", "hard", "hard"])

# 4. Call Turn 2
print("\nCalling Examiner for Question 2...")
examiner_messages, tool_use_id, q2_json, model_used = call_examiner_qn(
    client=client,
    system_prompt=system_prompt,
    examiner_messages=examiner_messages,
    pending_tool_use_id=tool_use_id,
    student_answer=simulated_student_answer,
    topic_options=q2_options,
    turn=2,
    picker=picker,
    temperature=0.2,
)

print("\n=== EXAM TURN 2 RESULT ===")
print(f"Action: {q2_json.get('action')} on {q2_json.get('actionParameters')}")
print(f"Evaluation of Q1: score={q2_json.get('internalEvaluation', {}).get('understandingScore')}, "
      f"authorship={q2_json.get('internalEvaluation', {}).get('authorshipConfidence')}")
print(f"Difficulty chosen for Q2: {q2_json.get('chosenTopicDifficulty')}")
print(f"\nQuestion 2:\n{q2_json.get('questionText')}")
print("\nExaminer Internal Reasoning:")
print(json.dumps(q2_json.get("internalReasoning"), indent=2))