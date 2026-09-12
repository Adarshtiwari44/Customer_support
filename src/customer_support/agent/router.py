import re
from customer_support.agent.state import AgentState


HUMAN_REQUEST_PATTERNS = [
    r"\bspeak to a (human|real person|manager|representative|supervisor|agent)\b",
    r"\bi (want|need|demand) to (talk|speak|chat) (to|with) a (human|person|manager|supervisor|agent|representative|someone)\b",
    r"\breal person\b",
    r"\bhuman assistance\b",
    r"\b(get|put) me (through|in touch) (to|with)\b",
    r"\btransfer me\b",
    r"\bescalat(e|ion)\b",
    r"\blet me (talk|speak) to\b",
    r"\bconnect me (to|with)\b",
    r"\b(need|want) (a |an )?(actual|real) (human|person|agent)\b",
    r"\bsomeone (else|real|who can help)\b",
]

# Intents that carry financial risk - escalate ONLY if no missing entities
FINANCIAL_RISK_INTENTS = {"payment_billing", "refund_return"}

# Intents that always require human review - security or complaint sensitivity
ALWAYS_ESCALATE_INTENTS = {
    "customer_service_complaint",  # Angry/frustrated customers need human empathy & authority
    "account_access",              # Security-sensitive: locked accounts, unauthorized access
    "human_assistance_request",    # Customer explicitly asking for human - always honor
}


def _detect_explicit_human_request(message: str) -> bool:
    lower = message.lower()
    return any(re.search(p, lower) for p in HUMAN_REQUEST_PATTERNS)


def route_decision(state: AgentState) -> AgentState:
    """
    Smart routing: AUTO_HANDLE vs NEED_INFORMATION vs ESCALATE.

    CRITICAL CHANGE: Does NOT escalate on weak evidence alone.
    Missing information triggers NEED_INFORMATION, not escalation.
    """
    errors = list(state.get("errors", []))
    current_message = state.get("current_message", "")
    intent = state.get("intent", "UNKNOWN")
    confidence = state.get("confidence", 0.0)
    confidence_tier = state.get("confidence_tier", "LOW")
    evidence_quality = state.get("evidence_quality", "NONE")
    response_valid = state.get("response_valid", False)
    high_risk = state.get("high_risk", False)
    missing_entities = state.get("missing_entities", [])

    explicit_human_request = _detect_explicit_human_request(current_message)

    reasons = []

    # Rule 1: Explicit human request - HARD override
    if explicit_human_request:
        reasons.append("explicit human assistance request detected")

    # Rule 2: Intent UNKNOWN with VERY LOW confidence (not just unknown alone)
    if intent == "UNKNOWN" and confidence < 0.3:
        reasons.append(f"intent is UNKNOWN with very low confidence ({confidence:.2f})")

    # Rule 3: Response validator failed (hallucination/forbidden claims)
    if not response_valid:
        reasons.append("response failed validation")

    # Rule 4: High-risk validator flag
    if high_risk:
        reasons.append("high-risk signal from validator")

    # Rule 5: Financial-risk intents - only escalate if we have all required info
    # If missing entities, ask first before escalating
    if intent in FINANCIAL_RISK_INTENTS and not missing_entities:
        reasons.append(f"financial-risk intent ({intent}) requires human review")

    # Rule 6: Always-escalate intents (complaints, account security)
    if intent in ALWAYS_ESCALATE_INTENTS:
        reasons.append(f"sensitive intent ({intent}) requires human review")

    # Rule 7: Critical pipeline errors (fail-closed on genuine failures)
    # BUT: if classifier used regex fallback successfully (conf >= 0.7), don't escalate on rate limits
    critical_errors = [e for e in errors if "failed" in e.lower() or "error" in e.lower()]

    # Filter out rate limit errors if we have a good fallback intent
    if critical_errors and intent != "UNKNOWN" and confidence >= 0.7:
        # We recovered via fallback - not a critical failure
        rate_limit_errors = [e for e in critical_errors if "ratelimit" in e.lower() or "rate limit" in e.lower()]
        if len(rate_limit_errors) == len(critical_errors):
            # All errors are just rate limits, and we have good fallback
            critical_errors = []

    if critical_errors:
        reasons.append(f"critical pipeline errors present")

    # *** REMOVED: weak evidence auto-escalation (lines 69-70 deleted) ***
    # Normal queries with weak evidence should request clarification, not escalate

    # Determine routing state
    if reasons:
        decision = "ESCALATE"
        escalation_reason = "; ".join(reasons)
        conversation_status = "ESCALATED"
    elif missing_entities:
        # Need more information - ask for it, don't escalate
        decision = "NEED_INFORMATION"
        escalation_reason = None
        conversation_status = "NEED_INFO"
    else:
        decision = "AUTO_HANDLE"
        escalation_reason = None
        conversation_status = "ACTIVE"

    return {
        **state,
        "decision": decision,
        "escalation_reason": escalation_reason,
        "conversation_status": conversation_status,
        "explicit_human_request": explicit_human_request,
        "errors": errors,
    }
