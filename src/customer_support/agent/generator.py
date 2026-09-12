import json
from langchain_groq import ChatGroq
from customer_support.config.setting import settings
from customer_support.agent.state import AgentState


GENERATOR_SYSTEM_PROMPT = """You are drafting a customer support reply for Amazon.

STRICT RULES (violating these is a critical failure):
- NEVER invent policies, fees, timelines, refund amounts, or eligibility rules.
- NEVER claim an action (refund, replacement, cancellation) has been completed — you can only DRAFT a response, not execute actions.
- Base your response ONLY on the current message, conversation context, and the historical evidence provided.
- If the evidence is weak, contradictory, or absent, explicitly state the limitation in your response rather than inventing a resolution.
- Treat historical evidence as precedent, not as guaranteed current policy.
- Keep the tone professional, empathetic, and concise (matching Amazon support style).

Respond ONLY with valid JSON in this exact format, nothing else:
{"draft_response": "<the reply text>", "claims": ["<factual claim 1>", "..."], "limitations": ["<any stated limitation, or empty list>"], "grounding_refs": ["<evidence_id used, or empty list>"]}
"""

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGroq(api_key=settings.GROQ_API_KEY, model=settings.LLM_MODEL, temperature=0.3)
    return _llm


def generate_response(state: AgentState) -> AgentState:
    """
    Generate context-aware response.
    - If missing entities: generate clarification question (NEED_INFO state)
    - Otherwise: generate evidence-based response
    """
    current_message = state.get("current_message", "")
    intent = state.get("intent", "UNKNOWN")
    evidence = state.get("evidence", [])
    evidence_quality = state.get("evidence_quality", "NONE")
    context_turns = state.get("relevant_context", [])
    missing_entities = state.get("missing_entities", [])
    collected_entities = state.get("collected_entities", {})
    conversation_status = state.get("conversation_status", "ACTIVE")
    errors = list(state.get("errors", []))

    if not current_message or not current_message.strip():
        return {
            **state,
            "draft_response": None,
            "claims": [],
            "limitations": ["no message to respond to"],
            "grounding_refs": [],
            "errors": errors + ["generator: skipped, empty message"],
        }

    # NEED_INFO state: Generate clarification question
    if conversation_status == "NEED_INFO" and missing_entities:
        clarification_prompts = {
            "order_id": "To help you with this, please provide your Order ID.",
            "marketplace": "Which marketplace was this order placed on (e.g., amazon.com, amazon.co.uk)?",
            "tracking_number": "Please provide your tracking number.",
            "email": "Please provide the email address associated with your account.",
            "phone": "Please provide your phone number.",
        }

        # Build clarification message
        question_parts = []
        for entity in missing_entities[:2]:  # Ask for max 2 things at once
            if entity in clarification_prompts:
                question_parts.append(clarification_prompts[entity])

        if not question_parts:
            question_parts = ["Could you provide more details?"]

        # Acknowledge what we know so far
        context_ack = ""
        if intent and intent != "UNKNOWN":
            intent_label = intent.replace("_", " ").title()
            context_ack = f"I understand you're asking about {intent_label.lower()}. "

        if collected_entities:
            collected_items = ", ".join(f"{k}: {v}" for k, v in collected_entities.items())
            context_ack += f"I have: {collected_items}. "

        draft_response = context_ack + " ".join(question_parts)

        return {
            **state,
            "draft_response": draft_response,
            "claims": [],
            "limitations": [f"missing required information: {', '.join(missing_entities)}"],
            "grounding_refs": [],
            "errors": errors,
        }

    # Otherwise, generate normal evidence-based response
    context_str = ""
    if context_turns:
        context_str = "\n\nConversation context:\n" + "\n".join(
            f"[{t['role']}] {t['cleaned_text']}" for t in context_turns
        )

    evidence_str = "\n\nHistorical evidence (from similar past cases):\n"
    if evidence:
        for e in evidence:
            evidence_str += f"- [{e['evidence_id']}] {e['resolution_text']}\n"
    else:
        evidence_str += "None available.\n"

    # Add collected entities to context
    entities_str = ""
    if collected_entities:
        entities_str = f"\n\nCollected customer information: {collected_entities}"

    user_prompt = (
        f"Customer's current message: \"{current_message}\"\n"
        f"Detected intent: {intent}\n"
        f"Evidence quality: {evidence_quality}"
        f"{context_str}{evidence_str}{entities_str}"
    )

    try:
        llm = _get_llm()
        response = llm.invoke([
            {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        raw = response.content.strip()

        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)

        return {
            **state,
            "draft_response": parsed.get("draft_response"),
            "claims": parsed.get("claims", []),
            "limitations": parsed.get("limitations", []),
            "grounding_refs": parsed.get("grounding_refs", []),
            "errors": errors,
        }

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        errors.append(f"generator: failed to parse LLM output ({type(e).__name__}) -> no draft")
        return {
            **state,
            "draft_response": None,
            "claims": [],
            "limitations": ["response generation failed"],
            "grounding_refs": [],
            "errors": errors,
        }
    except Exception as e:
        errors.append(f"generator: LLM call failed ({type(e).__name__}) -> no draft")
        return {
            **state,
            "draft_response": None,
            "claims": [],
            "limitations": ["response generation failed"],
            "grounding_refs": [],
            "errors": errors,
        }
