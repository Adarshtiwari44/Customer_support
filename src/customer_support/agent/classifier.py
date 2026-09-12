import json
import re
from langchain_groq import ChatGroq
from customer_support.config.setting import settings
from customer_support.agent.state import AgentState


TAXONOMY = [
    "delivery_status", "order_issue", "refund_return", "payment_billing",
    "pricing_query", "prime_membership", "content_streaming_issue",
    "device_tech_support", "repair_service_status", "account_access",
    "availability_question", "promo_discount_query", "feature_request",
    "product_issue", "customer_service_complaint", "human_assistance_request",
]

CLASSIFIER_SYSTEM_PROMPT = f"""You are a conversational intent classifier for Amazon customer support messages.

Classify the customer's CURRENT message into exactly ONE of these intents:
{", ".join(TAXONOMY)}

CRITICAL CONTEXTUAL RULES:
1. If the customer is providing an answer to a previous question (e.g., providing an Order ID, marketplace like amazon.com, email, confirmation, or short detail), MAINTAIN the ongoing conversation intent instead of classifying as UNKNOWN.
2. Only change the intent if there is clear, explicit evidence that the customer started a completely new, unrelated request.
3. If the message doesn't clearly fit any category, or is too vague to classify, respond with "UNKNOWN".

Respond ONLY with valid JSON in this exact format, nothing else:
{{"intent": "<intent_name_or_UNKNOWN>", "confidence": <float 0.0 to 1.0>, "reasoning": "<one short sentence>"}}
"""

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGroq(api_key=settings.GROQ_API_KEY, model=settings.LLM_MODEL, temperature=0)
    return _llm


def _confidence_tier(confidence: float) -> str:
    if confidence >= 0.75:
        return "HIGH"
    elif confidence >= 0.5:
        return "MEDIUM"
    else:
        return "LOW"


def classify_intent(state: AgentState) -> AgentState:
    """
    Context-aware intent classification.
    Considers the entire conversation state, current intent, and slots.
    Does NOT overwrite active intent on short slot-filling answers.
    """
    current_message = state.get("current_message", "").strip()
    existing_intent = state.get("current_intent")
    collected_entities = state.get("collected_entities", {})
    missing_entities = state.get("missing_entities", [])
    errors = list(state.get("errors", []))

    # Edge case: empty message
    if not current_message:
        return {
            **state,
            "intent": existing_intent or "UNKNOWN",
            "confidence": 0.0,
            "confidence_tier": "LOW",
            "secondary_intents": [],
            "is_followup_answer": False,
            "errors": errors + ["classifier: skipped, empty message"],
        }

    # Fast-path check: Is this a short slot response (e.g., order ID, marketplace, yes/no)?
    words = current_message.split()
    is_short = len(words) <= 5
    looks_like_id_or_marketplace = bool(
        re.match(r'^[A-Z0-9\-\.]{4,30}$', current_message, re.IGNORECASE) or
        "amazon." in current_message.lower() or
        "order" in current_message.lower() and len(words) <= 4 or
        current_message.isdigit()
    )

    if existing_intent and existing_intent in TAXONOMY and (is_short or looks_like_id_or_marketplace):
        # Customer is answering a follow-up or providing an entity
        return {
            **state,
            "intent": existing_intent,
            "confidence": 0.95,
            "confidence_tier": "HIGH",
            "secondary_intents": [],
            "is_followup_answer": True,
            "errors": errors,
        }

    # Build comprehensive prompt including conversation context and active task
    context_parts = []
    if existing_intent:
        context_parts.append(f"Ongoing conversation intent: {existing_intent}")
    if collected_entities:
        context_parts.append(f"Collected information so far: {collected_entities}")
    if missing_entities:
        context_parts.append(f"Information previously requested from customer: {missing_entities}")

    relevant_context = state.get("relevant_context", [])
    if relevant_context:
        context_str = "\nConversation history:\n" + "\n".join(
            f"[{t['role']}] {t['cleaned_text']}" for t in relevant_context
        )
        context_parts.append(context_str)

    context_block = "\n".join(context_parts)
    if context_block:
        user_prompt = f"Current customer message: \"{current_message}\"\n\nContext:\n{context_block}"
    else:
        user_prompt = f"Current customer message: \"{current_message}\""

    try:
        llm = _get_llm()
        response = llm.invoke([
            {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        raw = response.content.strip()

        # Handle markdown code fence
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        intent = parsed.get("intent", "UNKNOWN")
        confidence = float(parsed.get("confidence", 0.0))

        # Check for invalid taxonomy
        if intent not in TAXONOMY and intent != "UNKNOWN":
            errors.append(f"classifier: LLM returned invalid intent '{intent}', coercing to UNKNOWN")
            intent = "UNKNOWN"
            confidence = min(confidence, 0.3)

        confidence = max(0.0, min(1.0, confidence))

        # Contextual smoothing: if LLM returned UNKNOWN but we had an active ongoing intent and this was a brief reply, keep existing
        if intent == "UNKNOWN" and existing_intent and existing_intent in TAXONOMY:
            if is_short or confidence < 0.5:
                intent = existing_intent
                confidence = 0.85

        return {
            **state,
            "intent": intent,
            "confidence": confidence,
            "confidence_tier": _confidence_tier(confidence),
            "secondary_intents": [],
            "is_followup_answer": (intent == existing_intent and existing_intent is not None),
            "errors": errors,
        }

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # Fallback to existing intent if available, otherwise UNKNOWN
        fallback_intent = existing_intent if (existing_intent and existing_intent in TAXONOMY) else "UNKNOWN"
        fallback_conf = 0.7 if fallback_intent != "UNKNOWN" else 0.0
        errors.append(f"classifier: failed to parse LLM output ({type(e).__name__}) -> fallback to {fallback_intent}")
        return {
            **state,
            "intent": fallback_intent,
            "confidence": fallback_conf,
            "confidence_tier": _confidence_tier(fallback_conf),
            "secondary_intents": [],
            "is_followup_answer": bool(existing_intent),
            "errors": errors,
        }
    except Exception as e:
        # When LLM fails, try simple regex-based intent detection as fallback
        fallback_intent = existing_intent if (existing_intent and existing_intent in TAXONOMY) else None
        fallback_conf = 0.7 if fallback_intent else 0.0

        # Regex-based fallback patterns for common intents
        msg_lower = current_message.lower()

        # Human assistance request patterns
        if not fallback_intent and any(pattern in msg_lower for pattern in [
            "speak to", "talk to", "human", "agent", "representative", "real person",
            "transfer", "escalate", "manager", "supervisor"
        ]):
            fallback_intent = "human_assistance_request"
            fallback_conf = 0.85

        # Delivery/order status patterns
        elif not fallback_intent and any(pattern in msg_lower for pattern in [
            "where is my order", "track", "delivery", "shipment", "shipping", "hasn't arrived",
            "not received", "order status"
        ]):
            fallback_intent = "delivery_status"
            fallback_conf = 0.8

        # Refund/return patterns
        elif not fallback_intent and any(pattern in msg_lower for pattern in [
            "refund", "return", "send back", "money back", "cancel order"
        ]):
            fallback_intent = "refund_return"
            fallback_conf = 0.8

        # If still no match, use UNKNOWN
        if not fallback_intent:
            fallback_intent = "UNKNOWN"
            fallback_conf = 0.0

        errors.append(f"classifier: LLM call failed ({type(e).__name__}) -> regex fallback to {fallback_intent}")
        return {
            **state,
            "intent": fallback_intent,
            "confidence": fallback_conf,
            "confidence_tier": _confidence_tier(fallback_conf),
            "secondary_intents": [],
            "is_followup_answer": bool(existing_intent),
            "errors": errors,
        }
