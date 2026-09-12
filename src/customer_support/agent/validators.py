import re
from customer_support.agent.state import AgentState


# Words/phrases jo indicate karte hai ki response ne koi IRREVERSIBLE action
# "complete" hone ka claim kiya - MVP ko ye kabhi nahi karna chahiye
FORBIDDEN_COMPLETION_PHRASES = [
    r"\byour refund has been (processed|issued|completed)\b",
    r"\byour replacement has been (sent|shipped|arranged)\b",
    r"\bi have (cancelled|canceled) your\b",
    r"\byour order has been (cancelled|canceled)\b",
    r"\bi've (processed|issued) (a |your )?refund\b",
]


def validate_response(state: AgentState) -> AgentState:
    """
    Generated draft response ko safety checks se pass karta hai:
    - Response exist karta hai (generation fail nahi hua)?
    - Koi forbidden 'action completed' claim toh nahi kar raha?
    - Grounding refs valid hai (jo evidence generator ne cite ki, wo actually retrieve hui thi)?
    - Response khali/bahut chota toh nahi?
    """
    errors = list(state.get("errors", []))
    draft_response = state.get("draft_response")
    grounding_refs = state.get("grounding_refs", [])
    evidence = state.get("evidence", [])

    # Check 1: Response generate hi nahi hua (generator fail ho chuka tha)
    if not draft_response or not draft_response.strip():
        return {
            **state,
            "response_valid": False,
            "errors": errors + ["validator: no draft response to validate"],
        }

    # Check 2: Forbidden completion-claim phrases (PRD: never claim irreversible action done)
    lower_response = draft_response.lower()
    for pattern in FORBIDDEN_COMPLETION_PHRASES:
        if re.search(pattern, lower_response):
            return {
                **state,
                "response_valid": False,
                "high_risk": True,
                "errors": errors + [f"validator: response contains forbidden completion claim (pattern: {pattern})"],
            }

    # Check 3: Grounding refs valid hai - jo cite kiya wo actually retrieve hua tha?
    valid_evidence_ids = {e["evidence_id"] for e in evidence}
    for ref in grounding_refs:
        if ref not in valid_evidence_ids:
            errors.append(f"validator: grounding_ref '{ref}' not found in retrieved evidence (hallucinated citation)")
            return {
                **state,
                "response_valid": False,
                "high_risk": True,
                "errors": errors,
            }

    # Check 4: Response bahut chota/generic toh nahi (min length heuristic)
    if len(draft_response.strip()) < 15:
        return {
            **state,
            "response_valid": False,
            "errors": errors + ["validator: response too short/low-information"],
        }

    # Sab checks pass
    return {
        **state,
        "response_valid": True,
        "errors": errors,
    }