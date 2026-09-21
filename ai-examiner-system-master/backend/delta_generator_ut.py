import os
import json
import anthropic

def generate_delta_pool(failed_name: str, failed_code: str, accepted_name: str, accepted_code: str, readme: str) -> dict:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "delta_generation_prompt_ut.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    headers = {"anthropic-workspace-id": workspace_id} if workspace_id else None
    
    client = anthropic.Anthropic(api_key=api_key, default_headers=headers)

    user_content = (
        f"[PROBLEM DESCRIPTION]\n{readme}\n\n"
        f"[{failed_name.upper()}]\n{failed_code}\n\n"
        f"[{accepted_name.upper()}]\n{accepted_code}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}]
    )

    raw_text = response.content[0].text
    if raw_text.startswith("```json"):
        raw_text = raw_text.split("```json")[1].rsplit("```", 1)[0].strip()
    elif raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1].rsplit("```", 1)[0].strip()

    return json.loads(raw_text)