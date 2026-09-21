import os
import json
import anthropic
from dotenv import load_dotenv

from plan_assembler import QuestionPicker, load_pool
from agents import call_examiner_q1

load_dotenv()

# Absolute paths
failed_path = r"C:\Users\הניה\Desktop\ai_examiner\submissions\Rohithk01\failed.java"
accepted_path = r"C:\Users\הניה\Desktop\ai_examiner\submissions\Rohithk01\accepted.java"
readme_path = os.path.join(os.path.dirname(__file__), "assignments", "austin-a_readme.md")
pool_path = os.path.join(os.path.dirname(__file__), "assignments", "austin-a_question_pool.json")
prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "examiner_prompt_ut.txt")

# Read inputs
with open(failed_path, "r", encoding="utf-8", errors="replace") as f:
    failed_code = f.read()

with open(accepted_path, "r", encoding="utf-8", errors="replace") as f:
    accepted_code = f.read()

with open(readme_path, "r", encoding="utf-8") as f:
    readme = f.read()

with open(prompt_path, "r", encoding="utf-8") as f:
    system_prompt = f.read()

# Build exam context (Matches submission_source.py behavior)
student_files = {
    "failed.java": failed_code,
    "accepted.java": accepted_code,
}

full_context = f"[PROBLEM DESCRIPTION]\n{readme}\n\n[STUDENT SUBMITTED FILES]\n"
for name, content in student_files.items():
    full_context += f"\n--- File: {name} ---\n{content}\n"

# Load pool and pick Q1 options
pool = load_pool(pool_path)
picker = QuestionPicker(pool, seed=42, silent=True)
q1_options = picker.peek_options(["medium", "medium"])

# Initialize Anthropic Client
api_key = os.environ.get("ANTHROPIC_API_KEY")
workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None

client = anthropic.Anthropic(api_key=api_key, default_headers=headers)

print("Calling Examiner for Question 1...")
# Call the actual system method
messages, tool_id, examiner_json, model_used = call_examiner_q1(
    client=client,
    system_prompt=system_prompt,
    full_context=full_context,
    q1_options=q1_options,
    picker=picker,
    temperature=0.2,
)

print("\n=== EXAM TURN 1 RESULT ===")
print(f"Model used: {model_used}")
print(f"Action: {examiner_json.get('action')} on {examiner_json.get('actionParameters')}")
print(f"\nQuestion {examiner_json.get('questionNumber')}:")
print(examiner_json.get("questionText"))
print("\nExaminer Internal Reasoning:")
print(json.dumps(examiner_json.get("internalReasoning"), indent=2))