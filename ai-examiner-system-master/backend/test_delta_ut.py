import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

failed_path = r"C:\Users\הניה\Desktop\ai_examiner\submissions\Rohithk01\A__2025-10-06_16-48-45__WA_t1__sid342362690.java"
accepted_path = r"C:\Users\הניה\Desktop\ai_examiner\submissions\Rohithk01\A__2025-10-11_21-33-13__AC__sid343216156.java"
html_path = r"C:\Users\הניה\Desktop\ai_examiner\submissions\Rohithk01\._index.html"

with open(failed_path, "r", encoding="utf-8", errors="replace") as f:
    failed_code = f.read()

with open(accepted_path, "r", encoding="utf-8", errors="replace") as f:
    accepted_code = f.read()

with open(html_path, "r", encoding="utf-8", errors="replace") as f:
    problem_html = f.read()

DELTA_SYSTEM_PROMPT = """You are an expert Competitive Programming coach and Computer Science examiner. 
Your task is to generate a custom pool of EXACTLY 4 oral-exam questions by comparing a student's FAILED submission against their ACCEPTED submission.

INPUTS:
1. PROBLEM DESCRIPTION (HTML/Text)
2. FAILED SUBMISSION (WA/TLE/RE/CE)
3. ACCEPTED SUBMISSION (AC)

THE OBJECTIVE:
Generate questions that verify the student actually understands WHY their first submission failed and HOW their second submission fixed it. Focus on:
1. Flawed Logic: Articulate why the original logic fails or give a counterexample.
2. Corner Cases: Missed boundary conditions (e.g. no valid answer exists).
3. Algorithmic Inefficiency: Asymptotic complexity O(N) vs O(log N).
4. Success Justification: Correctness argument for why the fix succeeds and input bounds.

OUTPUT FORMAT (JSON ONLY):
Output exactly ONE JSON object matching this schema. Do not output markdown fences or conversational text.
{
  "questions": [
    {
      "id": "q1_delta",
      "files": ["failed.java", "accepted.java"],
      "focus": "<The specific usage/mechanism being compared>",
      "dimension": "<MUST BE ONE OF: design_choice, edge_case, error_handling, api_depth, code_flow, cross_file, counterfactual_mutation>",
      "difficulty": "<easy, medium, or hard>",
      "anchor": "<The exact lines or conceptual shift between the two files>",
      "examiner_notes": "<Directional briefing for the examiner on what to listen for.>",
      "bad_versions_to_avoid": "<Common trap answers to watch out for>",
      "conflicts_with": []
    }
  ]
}
"""

def generate_and_save_pool():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    
    headers = {}
    if workspace_id:
        headers["anthropic-workspace-id"] = workspace_id

    client = anthropic.Anthropic(api_key=api_key, default_headers=headers if headers else None)

    user_content = (
        f"[PROBLEM DESCRIPTION]\n{problem_html}\n\n"
        f"[FAILED SUBMISSION]\n{failed_code}\n\n"
        f"[ACCEPTED SUBMISSION]\n{accepted_code}"
    )

    print("Analyzing delta and generating question pool...")
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=4096,
        system=DELTA_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    text_content = next(
        (block.text for block in response.content if getattr(block, "type", None) == "text"),
        ""
    ).strip()

    # Clean markdown formatting if present
    if text_content.startswith("```"):
        text_content = text_content.split("```")[1]
        if text_content.startswith("json"):
            text_content = text_content[4:]
        text_content = text_content.strip()

    try:
        parsed_json = json.loads(text_content)
        
        # Save to backend/assignments/austin-a_question_pool.json
        output_dir = os.path.join(os.path.dirname(__file__), "assignments")
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "austin-a_question_pool.json")
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(parsed_json, f, indent=2, ensure_ascii=False)
            
        print(f"SUCCESS: Question pool saved to {output_file}")
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        print("Raw text returned:")
        print(text_content)

if __name__ == "__main__":
    generate_and_save_pool()