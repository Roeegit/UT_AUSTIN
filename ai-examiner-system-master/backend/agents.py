"""
agents.py — Extracted LLM agent logic for the stateless backend.

Contains:
  - Pydantic schemas (ExaminerOutput, GraderOutput, CodeReviewerOutput)
  - call_agent()         — Anthropic call → Sonnet fallback → Gemini fallback on 529
  - call_examiner_q1()   — First examiner turn (builds full context message)
  - call_examiner_qn()   — Subsequent examiner turns (with student answer + topic options)
  - call_grader()        — Grader agent after exam completion
  - call_code_reviewer() — Phase 1 static code review
  - compute_final_grade() — Mechanical grade formula (no LLM
  - serialize_messages()  — Convert Anthropic SDK objects to plain dicts for DB
"""

import json
import os
import random
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, Field

from config import (
    ANTHROPIC_FALLBACK_MODEL,
    CODE_REVIEWER_MODEL,
    EXAMINER_MODEL,
    FORCE_GEMINI_FALLBACK,
    FORCE_SONNET,
    GEMINI_FALLBACK_MODEL,
    GRADER_MODEL,
)

# ----------------------------------------------------------------------------
# Pydantic Schemas — must match the system prompts exactly
# ---------------------------------------------------------------------------

class InternalReasoning(BaseModel):
    assignmentAnalysis: str
    studentEvaluationSoFar: str
    chosenTopicFocus: str
    adaptiveDifficultyStrategy: str
    planForNextQuestion: str


class ActionParameters(BaseModel):
    fileName: Optional[str] = None
    codeLine: Optional[str] = None


class InternalEvaluation(BaseModel):
    understandingScore: Optional[float] = Field(default=None)
    authorshipConfidence: Optional[Literal["high", "medium", "low"]] = Field(default=None)
    integrityFlag: bool = Field(default=False)
    suspectedPromptInjection: bool = Field(default=False)
    notes: str = Field(default="")


class ExaminerOutput(BaseModel):
    internalReasoning: InternalReasoning
    questionNumber: int
    questionText: str
    action: str = Field(
        description="Must be 'JUMP_TO_LINE', 'NONE', 'RE_ASK', 'FINISH_EXAM', "
                    "or 'END_EXAM_DISTRESS'"
    )
    actionParameters: ActionParameters
    internalEvaluation: InternalEvaluation
    bugPivotUsed: bool = Field(default=False)
    switchGranted: bool = Field(default=False)
    # Which labelled topic option the examiner picked. The prompt has always documented this
    # field and main.py reads it (to record `chosen_topic` and to mark that topic used), but it
    # was missing from this schema — so a schema-constrained model could not emit it at all.
    # Every exam silently fell back to option index 0, recording a topic that frequently was
    # NOT the one the question came from, which corrupted transcripts, item-analysis stats and
    # the picker's used-topic bookkeeping. Restored 2026-08-20.
    chosenTopicLabel: Optional[Literal[
        "easy-1", "easy-2", "medium-1", "medium-2", "hard-1", "hard-2"
    ]] = Field(default=None)
    chosenTopicDifficulty: Optional[Literal["easy", "medium", "hard"]] = Field(default=None)
    nextQuestionDifficulty: Optional[Literal["easy", "medium", "hard"]] = Field(default=None)
    # Every examiner prompt documents this as "Always required" and pairs
    # studentPersona "distressed" with action END_EXAM_DISTRESS, but it was missing from
    # this schema. Nothing reads it programmatically — it is the audit trail for why a
    # turn was handled as a switch / hostility / distress event — and because the schema
    # does not forbid extra properties the model emitted it only sometimes (present in 5
    # of the Linear Algebra turns sampled, absent from the Operating Systems ones).
    # Declaring it makes that record reliable instead of incidental.
    studentPersona: Optional[Literal[
        "neutral", "cooperative_switch", "hostile", "distressed"
    ]] = Field(default="neutral")


class SignalBAssessment(BaseModel):
    markersFound: int
    level: Literal["none", "low", "moderate", "high"]
    analysis: str


class CodeReviewerOutput(BaseModel):
    staticCodeQualityScore: int
    studentStaticFeedback: str
    codeReviewNotes: str
    signalBAssessment: SignalBAssessment


class ReviewerChallenge(BaseModel):
    deduction: str
    category: Literal["provided_material", "spec_mandated", "not_required", "wrong_convention"]
    evidence: str
    confidence: Literal["high", "medium"]


class ReviewerValidatorOutput(BaseModel):
    """Output of the second code-review validator (hallucination guard). Audits the first
    reviewer's deductions for over-penalization only (never re-reviews for missed problems)
    and, when it finds unfair deductions, restores the wrongly-removed points and minimally
    edits the student feedback. It can only RAISE the score, never lower it."""
    challenges: list[ReviewerChallenge]
    any_unfair_deductions: bool
    corrected_static_score: int          # >= original; equals original if nothing unfair
    corrected_student_feedback: str      # minimally-edited Hebrew feedback; "" to keep original
    summary: str


class GradingScratchpad(BaseModel):
    transcript_analysis: str
    difficulty_trajectory: str
    irt_floor_calculation: str
    authorship_signal_check: str


class GraderOutput(BaseModel):
    grading_scratchpad: GradingScratchpad
    authorshipAssessment: Literal["established", "partial", "not_established"]
    integrityFlag: bool
    promptInjectionFlag: bool
    academicDishonestyReasoning: str
    oralDefenseScore: int
    studentFeedback: str
    professorReport: str


# ---------------------------------------------------------------------------
# Helper: convert Pydantic model → Anthropic tool definition
# ---------------------------------------------------------------------------
def pydantic_to_anthropic_tool(model_class: type[BaseModel], tool_name: str, description: str) -> dict:
    schema = model_class.model_json_schema()
    schema.pop("title", None)

    # --- BRUTE-FORCE $DEFS FLATTENER ---
    if "$defs" in schema:
        defs = schema.pop("$defs")
        schema_str = json.dumps(schema)
        
        # Find the exact JSON string for each reference and swap it with its definition
        for def_key, def_val in defs.items():
            ref_str = json.dumps({"$ref": f"#/$defs/{def_key}"})
            val_str = json.dumps(def_val)
            schema_str = schema_str.replace(ref_str, val_str)
            
        schema = json.loads(schema_str)
    # ----------------------------------

    return {
        "name": tool_name,
        "description": description,
        "input_schema": schema,
    }


# Pre-build tool dicts (done once at import time)
EXAMINER_TOOL = pydantic_to_anthropic_tool(
    ExaminerOutput,
    "submit_examiner_output",
    "Submit the structured examiner output, including the next question, "
    "internal reasoning, and evaluation of the student's last answer.",
)
GRADER_TOOL = pydantic_to_anthropic_tool(
    GraderOutput,
    "submit_grader_verdict",
    "Submit the final grading verdict including the numeric grade and "
    "the professor report written in Hebrew.",
)
CODE_REVIEWER_TOOL = pydantic_to_anthropic_tool(
    CodeReviewerOutput,
    "submit_code_review",
    "Submit the static code quality score, review notes, and Signal B style origin assessment.",
)
REVIEWER_VALIDATOR_TOOL = pydantic_to_anthropic_tool(
    ReviewerValidatorOutput,
    "submit_review_validation",
    "Submit the audit of the first reviewer's deductions: any unfair (over-penalizing) "
    "deductions found, with evidence.",
)


# ---------------------------------------------------------------------------
# Message serialization — SDK objects → plain dicts for JSON/DB storage
# ---------------------------------------------------------------------------

def _block_to_dict(block) -> dict:
    """Convert an Anthropic SDK content block object to a plain dict."""
    if isinstance(block, dict):
        return block
    d: dict = {"type": block.type}
    if block.type == "text":
        d["text"] = block.text
    elif block.type == "tool_use":
        d["id"] = block.id
        d["name"] = block.name
        d["input"] = block.input
    elif block.type == "tool_result":
        d["tool_use_id"] = block.tool_use_id
        d["content"] = block.content
    return d


def serialize_messages(messages: list) -> list:
    """Convert examiner_messages (may contain SDK objects) to JSON-serializable list."""
    result = []
    for msg in messages:
        content = msg["content"]
        if isinstance(content, list):
            content = [_block_to_dict(b) for b in content]
        result.append({"role": msg["role"], "content": content})
    return result


# ---------------------------------------------------------------------------
# Gemini fallback helpers (mirrors exam_system.py exactly)
# ---------------------------------------------------------------------------

def _build_gemini_prompt(messages: list, system_prompt: str, tool: dict) -> str:
    """
    Flatten an Anthropic-format message history into a single text prompt for Gemini.
    Preserves full exam context so Gemini can generate the correct continuation.
    """
    parts = [f"[SYSTEM INSTRUCTIONS]\n{system_prompt}\n"]

    for msg in messages:
        label = "USER" if msg["role"] == "user" else "EXAMINER"
        content = msg["content"]

        if isinstance(content, str):
            parts.append(f"\n[{label}]\n{content}")
        elif isinstance(content, list):
            fragments = []
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type")
                    if btype == "text":
                        fragments.append(block.get("text", ""))
                    elif btype == "tool_use":
                        fragments.append(
                            f"[Previous examiner JSON output]\n"
                            f"{json.dumps(block.get('input', {}), ensure_ascii=False)}"
                        )
                    elif btype == "tool_result":
                        pass  # acknowledgement — not meaningful to Gemini
                else:
                    # Anthropic SDK object
                    if hasattr(block, "type"):
                        if block.type == "text":
                            fragments.append(block.text)
                        elif block.type == "tool_use":
                            fragments.append(
                                f"[Previous examiner JSON output]\n"
                                f"{json.dumps(block.input, ensure_ascii=False)}"
                            )
            if fragments:
                parts.append(f"\n[{label}]\n" + "\n".join(fragments))

    parts.append(
        f"\n\n[INSTRUCTION]\n"
        f"Respond with ONLY a valid JSON object matching this schema exactly. "
        f"No markdown fences, no explanation — just the raw JSON:\n"
        f"{json.dumps(tool['input_schema'], indent=2)}"
    )
    return "\n".join(parts)


def _call_gemini_fallback(messages: list, system_prompt: str, tool: dict, temperature: float) -> tuple:
    """
    Call Gemini as a drop-in fallback when all Anthropic models are overloaded.

    Returns (synthetic_content_list, fake_tool_use_id, parsed_dict) — same
    shape as the Anthropic path so callers need no special-casing.
    The synthetic content list is a valid Anthropic-format tool_use dict block
    so it can be appended to examiner_messages unchanged.
    """
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError(
            "Anthropic is overloaded and the Gemini fallback requires "
            "'google-generativeai'. Run:  pip install google-generativeai"
        )

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Gemini fallback requires GEMINI_API_KEY environment variable."
        )

    genai.configure(api_key=api_key)
    prompt = _build_gemini_prompt(messages, system_prompt, tool)

    gemini_model = genai.GenerativeModel(
        model_name=GEMINI_FALLBACK_MODEL,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )

    response = gemini_model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown fences if the model ignored response_mime_type
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)

    fake_id = f"gemini_{random.randint(100000, 999999)}"
    synthetic_content = [{
        "type": "tool_use",
        "id": fake_id,
        "name": tool["name"],
        "input": parsed,
    }]
    return synthetic_content, fake_id, parsed


# ---------------------------------------------------------------------------
# Core API call: Opus → Sonnet → Gemini on 529 overload
# ---------------------------------------------------------------------------

def call_agent(
    client: anthropic.Anthropic,
    model: str,
    system_prompt: str,
    messages: list,
    tool: dict,
    temperature: float,
) -> tuple:
    """
    Call the Anthropic API with tool-forcing.

    Cascade on 529 (overloaded):
      requested model  →  claude-sonnet-4-6  →  Gemini

    Returns (content_list, tool_use_id, parsed_dict, model_used).
    """
    if FORCE_SONNET:
        print(f"[DEBUG] FORCE_SONNET=True — using {ANTHROPIC_FALLBACK_MODEL}...")
        model = ANTHROPIC_FALLBACK_MODEL

    if FORCE_GEMINI_FALLBACK:
        print("[DEBUG] FORCE_GEMINI_FALLBACK=True — routing directly to Gemini...")
        content, fid, parsed = _call_gemini_fallback(messages, system_prompt, tool, temperature)
        return content, fid, parsed, GEMINI_FALLBACK_MODEL

    models_to_try = [model]
    if model != ANTHROPIC_FALLBACK_MODEL:
        models_to_try.append(ANTHROPIC_FALLBACK_MODEL)

    # --- DEBUG 1: EXAMINE THE EXACT OUTGOING SCHEMA ---
    print("\n" + "="*50)
    print("[DEBUG 1] OUTGOING TOOL SCHEMA TO ANTHROPIC:")
    print(json.dumps(tool.get("input_schema", {}), indent=2))
    print("="*50 + "\n")
    # --------------------------------------------------

    for current_model in models_to_try:
        try:
            response = client.messages.create(
                model=current_model,
                max_tokens=8169,
                system=[{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=messages,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},


                # NOTE: `temperature` is intentionally NOT forwarded here. Opus 5 / Sonnet 5
                # reject the `temperature` param outright (any value on Opus 5, any non-default
                # value on Sonnet 5) with a 400 — see docs/VERTEX_AI_MIGRATION.md. `temperature`
                # is still threaded through to the Gemini fallback below, which accepts it fine.
            )


            # --- DEBUG 2: EXAMINE THE EXACT INCOMING RESPONSE ---
            print("\n" + "="*50)
            print(f"[DEBUG 2] INCOMING RESPONSE FROM {current_model}:")
            print(f"Stop Reason: {response.stop_reason}")
            print(f"Usage: {response.usage}")
            print(f"Content: {response.content}")
            print("="*50 + "\n")

            if response.stop_reason == "refusal":
                print(f"[!] {current_model} safety classifier refused request. Trying fallback...")
                continue

            for block in response.content:
                if block.type == "tool_use":
                    # Reject empty inputs produced by mid-stream refusals
                    if not block.input:
                        print(f"[!] {current_model} returned empty tool input — trying fallback...")
                        continue
                    return response.content, block.id, block.input, current_model
            
            raise RuntimeError("No valid tool_use block in response.")
            # ----------------------------------------------------


            for block in response.content:
                if block.type == "tool_use":
                    return response.content, block.id, block.input, current_model
            raise RuntimeError("No tool_use block in response — this should not happen.")
        except anthropic.APIStatusError as e:
            if e.status_code not in (429, 529):
                raise
            label = "overloaded (529)" if e.status_code == 529 else "rate-limited (429)"
            print(f"[!] {current_model} {label} — trying next fallback...")

    # All Anthropic models overloaded — fall back to Gemini
    print(f"[!] All Anthropic models overloaded. Switching to Gemini ({GEMINI_FALLBACK_MODEL})...")
    content, fid, parsed = _call_gemini_fallback(messages, system_prompt, tool, temperature)
    return content, fid, parsed, GEMINI_FALLBACK_MODEL


# ---------------------------------------------------------------------------
# Examiner: Q1 (first turn — sends full student context)
# ---------------------------------------------------------------------------

def call_examiner_q1(
    client: anthropic.Anthropic,
    system_prompt: str,
    full_context: str,
    q1_options: list,  # list of 2 medium-difficulty question dicts (or None) from peek_options
    picker,            # QuestionPicker instance (for format_topic_for_examiner)
    temperature: float,
) -> tuple:
    """
    Builds the Q1 user message, calls the examiner, and returns everything needed
    to reconstruct state for the next turn.

    Returns:
        examiner_messages  — the updated message list (user + assistant)
        tool_use_id        — to be stored as pending_tool_use_id
        examiner_json      — the parsed examiner output dict
        model_used         — which model answered
    """
    _Q1_LABELS = ["medium-1", "medium-2"]
    option_parts = []
    for label, opt in zip(_Q1_LABELS, q1_options):
        if opt is not None:
            option_parts.append(
                f"[{label.upper()} OPTION]\n"
                f"{json.dumps(picker.format_topic_for_examiner(opt), ensure_ascii=False)}"
            )
        else:
            option_parts.append(f"[{label.upper()} OPTION]\n(not available — skip this option)")

    topic_text = (
        f"[TOPIC OPTIONS FOR QUESTION 1]\n"
        f"Two medium-difficulty options are provided. Pick the one whose topic and file are "
        f"most relevant to the student's actual code. Set `chosenTopicLabel` to the label you chose "
        f"(\"medium-1\" or \"medium-2\") and `chosenTopicDifficulty` to \"medium\".\n\n"
        + "\n\n".join(option_parts)
    )

    examiner_messages = [{
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": f"Please begin the exam based on the following context:\n\n{full_context}",
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": topic_text,
            },
        ],
    }]

    assistant_content, tool_use_id, examiner_json, model_used = call_agent(
        client, EXAMINER_MODEL, system_prompt, examiner_messages, EXAMINER_TOOL, temperature
    )

    # Append assistant turn (serialize immediately for consistent state)
    examiner_messages.append({
        "role": "assistant",
        "content": [_block_to_dict(b) for b in assistant_content],
    })

    return examiner_messages, tool_use_id, examiner_json, model_used


# ---------------------------------------------------------------------------
# Examiner: Q2+ (subsequent turns — sends student answer + topic options)
# ---------------------------------------------------------------------------

def call_examiner_qn(
    client: anthropic.Anthropic,
    system_prompt: str,
    examiner_messages: list,       # deserialized from DB (plain dicts)
    pending_tool_use_id: str,
    student_answer: str,
    topic_options: list,           # list of 3 question dicts (or None) from peek_options
    turn: int,
    picker,
    temperature: float,
    switch_used: bool = False,
    reask_pending: bool = False,
) -> tuple:
    """
    Builds the Qn user message, appends it to history, calls the examiner.

    `turn` is the NEXT question number (e.g. 2 when processing Q1's answer).
    `switch_used` injects the switch status and, when unused, the rule that a
    granted switch keeps questionNumber at turn-1 (the current question).
    `reask_pending` injects a RE_ASK STATUS block telling the examiner this is
    the student's second attempt — do not RE_ASK again.

    Returns:
        examiner_messages  — updated list (for saving back to DB)
        tool_use_id        — new pending_tool_use_id
        examiner_json      — parsed examiner output dict
        model_used         — model that responded
    """
    _OPTION_LABELS = ["easy-1", "easy-2", "medium-1", "medium-2", "hard-1", "hard-2"]
    option_parts = []
    for label, opt in zip(_OPTION_LABELS, topic_options):
        if opt is not None:
            option_parts.append(
                f"[{label.upper()} OPTION]\n"
                f"{json.dumps(picker.format_topic_for_examiner(opt), ensure_ascii=False)}"
            )
        else:
            option_parts.append(f"[{label.upper()} OPTION]\n(not available — skip this option)")

    # Build the switch status line injected into the topic block.
    # When the switch is still available, also tell the examiner which questionNumber
    # to use if it grants the switch (must stay at the CURRENT question, not advance).
    if switch_used:
        switch_status = "Switch already used: Yes"
    else:
        switch_status = (
            f"Switch already used: No\n"
            f"Switch rule: if you grant a switch (switchGranted: true), the student stays on "
            f"question {turn - 1}. Set questionNumber to {turn - 1} (not {turn}) in your JSON. "
            f"Pick an option at the same difficulty level you chose when you originally asked Q{turn - 1}. "
            f"The system has already provided fresh replacement options above."
        )

    options_text = (
        f"[TOPIC OPTIONS FOR QUESTION {turn}]\n"
        f"Six options are provided — two per difficulty level (easy-1/easy-2, medium-1/medium-2, hard-1/hard-2). "
        f"First decide which difficulty fits the student's demonstrated performance, then pick the specific option "
        f"whose topic and file are most relevant to the student's actual code. "
        f"Set `chosenTopicLabel` to the exact label you selected (e.g. \"medium-2\") "
        f"and set `chosenTopicDifficulty` to its difficulty portion (e.g. \"medium\").\n"
        f"{switch_status}\n\n"
        + "\n\n".join(option_parts)
    )

    # Build the user message content blocks
    user_content: list = [
        {
            "type": "tool_result",
            "tool_use_id": pending_tool_use_id,
            "content": "Question received by student.",
        },
        {
            "type": "text",
            "text": student_answer,
        },
        {
            "type": "text",
            "text": options_text,
        },
    ]

    # If the previous turn issued a RE_ASK, tell the examiner this is the
    # student's second (final) attempt — forbid another RE_ASK.
    if reask_pending:
        user_content.append({
            "type": "text",
            "text": (
                "[RE_ASK STATUS]\n"
                "The student's previous response was malformed or incomplete and a re-ask was issued. "
                "This is their SECOND and FINAL attempt at this question. "
                "You MUST NOT set action to RE_ASK again regardless of answer quality. "
                "Accept whatever the student says, score it on its technical merits "
                "(score 1 if still empty/gibberish), and proceed normally."
            ),
        })

    examiner_messages.append({"role": "user", "content": user_content})

    assistant_content, tool_use_id, examiner_json, model_used = call_agent(
        client, EXAMINER_MODEL, system_prompt, examiner_messages, EXAMINER_TOOL, temperature
    )

    examiner_messages.append({
        "role": "assistant",
        "content": [_block_to_dict(b) for b in assistant_content],
    })

    return examiner_messages, tool_use_id, examiner_json, model_used


# ---------------------------------------------------------------------------
# Code Reviewer (Phase 1 — blind to exam transcript)
# ---------------------------------------------------------------------------

def call_code_reviewer(
    client: anthropic.Anthropic,
    system_prompt: str,
    assignment_readme: str,
    student_files: dict,   # {filename: content}
) -> tuple:
    """
    Returns (code_review_json, model_used).
    code_review_json keys: staticCodeQualityScore, codeReviewNotes, signalBAssessment
    """
    context = "# Assignment Instructions\n" + assignment_readme + "\n\n"
    context += "# Student's Submitted Source Code\n"
    for filename, content in student_files.items():
        context += f"\n### {filename}\n```c\n{content}\n```\n"

    messages = [{"role": "user", "content": context}]

    try:
        _, _, code_review_json, model_used = call_agent(
            client, CODE_REVIEWER_MODEL, system_prompt, messages, CODE_REVIEWER_TOOL, 0.1
        )
    except Exception as e:
        code_review_json = {
            "staticCodeQualityScore": 50,
            "codeReviewNotes": f"Code reviewer error: {e}",
            "studentStaticFeedback": "",
            "signalBAssessment": {"markersFound": 0, "level": "none", "analysis": f"Error: {e}"},
        }
        model_used = "error"

    return code_review_json, model_used


# ---------------------------------------------------------------------------
# Reviewer Validator (Phase 1b — audits the code reviewer's deductions for
# over-penalization only; see MULTI_COURSE_MIGRATION §4.9)
# ---------------------------------------------------------------------------

def call_reviewer_validator(
    client: anthropic.Anthropic,
    system_prompt: str,
    assignment_readme: str,
    student_files: dict,           # {filename: content}
    code_review_json: dict,        # the first reviewer's output
    skeleton_files: dict | None = None,   # provided/starter material, when available
) -> tuple:
    """Returns (validation_json, model_used). validation_json keys: challenges,
    any_unfair_deductions, summary. On error returns an inert 'no challenges' result so a
    validator hiccup never changes grading. Runs on the primary model (Opus) by design —
    this is a correctness guard, not a place to save tokens."""
    original_score = code_review_json.get("staticCodeQualityScore")
    context = "# Assignment Instructions\n" + assignment_readme + "\n\n"
    if skeleton_files:
        context += "# Skeleton / Starter Material (NOT the student's work — never penalize)\n"
        for filename, content in skeleton_files.items():
            context += f"\n### {filename}\n```\n{content}\n```\n"
        context += "\n"
    context += "# Student's Submitted Work\n"
    for filename, content in student_files.items():
        context += f"\n### {filename}\n```\n{content}\n```\n"
    context += (
        "\n# First Reviewer's Output (audit its deductions)\n"
        f"staticCodeQualityScore: {original_score}\n"
        f"studentStaticFeedback:\n{code_review_json.get('studentStaticFeedback', '')}\n\n"
        f"codeReviewNotes:\n{code_review_json.get('codeReviewNotes', '')}\n"
    )

    messages = [{"role": "user", "content": context}]
    try:
        _, _, validation_json, model_used = call_agent(
            client, CODE_REVIEWER_MODEL, system_prompt, messages, REVIEWER_VALIDATOR_TOOL, 0.1
        )
    except Exception as e:  # inert on failure — never blocks or alters a grade
        validation_json = {"challenges": [], "any_unfair_deductions": False,
                           "corrected_static_score": original_score if isinstance(original_score, (int, float)) else 0,
                           "corrected_student_feedback": "",
                           "summary": f"validator error (ignored): {e}"}
        model_used = "error"
    return validation_json, model_used


# ---------------------------------------------------------------------------
# Grader (Phase 2 — sees README + Signal B + transcript, blind to code)
# ---------------------------------------------------------------------------

def call_grader(
    client: anthropic.Anthropic,
    system_prompt: str,
    assignment_readme: str,
    signal_b: dict,
    transcript: list,
    extra_notes: str = "",
) -> tuple:
    """
    Returns (grader_json, model_used).
    grader_json keys: grading_scratchpad, authorshipAssessment,
                      integrityFlag, promptInjectionFlag, academicDishonestyReasoning,
                      oralDefenseScore, professorReport

    extra_notes: optional block prepended before the Signal B section — used to
                 inject timeout status and switch-grant behavioral notes.
    """
    signal_b_block = (
        f"# Code Style Origin Analysis (Signal B)\n"
        f"Produced by an independent code reviewer who examined the student's source "
        f"files without access to any exam data.\n\n"
        f"Signal B Level: {signal_b.get('level', 'none')}\n"
        f"Markers Found: {signal_b.get('markersFound', 0)}\n"
        f"Analysis: {signal_b.get('analysis', 'No analysis available.')}"
    )

    second_block = ""
    if extra_notes:
        second_block += extra_notes.rstrip() + "\n\n"
    second_block += (
        f"{signal_b_block}\n\n"
        "--- Exam Transcript (Includes Examiner Internal Evaluations) ---\n"
        f"{json.dumps(transcript, indent=2, ensure_ascii=False)}\n"
    )

    grader_messages = [{
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": f"Please evaluate the following oral exam session.\n\n"
                        f"# Assignment Instructions\n{assignment_readme}",
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": second_block,
            },
        ],
    }]

    try:
        _, _, grader_json, model_used = call_agent(
            client, GRADER_MODEL, system_prompt, grader_messages, GRADER_TOOL, 0.1
        )
        print(f"[Grader] Model={model_used} keys={list(grader_json.keys())}")
    except Exception as e:
        grader_json = {
            "grading_scratchpad": {
                "transcript_analysis": f"Error: {e}",
                "difficulty_trajectory": "",
                "irt_floor_calculation": "",
                "authorship_signal_check": "",
            },
            "authorshipAssessment": "partial",
            "integrityFlag": False,
            "promptInjectionFlag": False,
            "academicDishonestyReasoning": "",
            "oralDefenseScore": 50,
            "professorReport": f"Grader error: {e}",
        }
        model_used = "error"

    return grader_json, model_used


# ---------------------------------------------------------------------------
# Phase 3: Mechanical grade combination (no LLM)
# ---------------------------------------------------------------------------

def compute_final_grade(oral_score: int, static_code_score: int) -> dict:
    """
    Combines oral defense score and static code quality into a final grade.
    Formula: 75% oral defense + 25% static code quality.
    """
    final_grade = round(1.0 * oral_score + 0.0 * static_code_score)

    return {
        "formula":                "round(1.0 * oralDefenseScore + 0.0 * staticCodeQualityScore)",
        "oralDefenseScore":       oral_score,
        "staticCodeQualityScore": static_code_score,
        "finalWeightedGrade":     final_grade,
    }
