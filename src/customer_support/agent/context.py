from customer_support.agent.state import AgentState, ConversationTurn


MAX_CONTEXT_TURNS = 6  # bahut purani/lambi conversation se sirf recent turns lenge


def build_context(state: AgentState) -> AgentState:
    """
    Current message + relevant preceding turns ko process karta hai.
    PRD requirement: relevant preceding turns consider karo jab woh current
    message ka meaning materially change karte hai; bahut purane/irrelevant
    turns ko over-weight mat karo.
    """
    context_turns = state.get("context_turns", [])
    current_message = state.get("current_message", "")

    errors = list(state.get("errors", []))

    # Edge case: current_message khali/missing hai
    if not current_message or not current_message.strip():
        errors.append("context_builder: current_message is empty or missing")
        return {
            **state,
            "relevant_context": [],
            "context_used": False,
            "errors": errors,
        }

    # Edge case: bahut lambi conversation — sirf recent N turns lo
    # (PRD: "avoid over-weighting irrelevant or very old turns")
    if len(context_turns) > MAX_CONTEXT_TURNS:
        relevant_context = context_turns[-MAX_CONTEXT_TURNS:]
    else:
        relevant_context = context_turns

    context_used = len(relevant_context) > 0

    return {
        **state,
        "relevant_context": relevant_context,
        "context_used": context_used,
        "errors": errors,
    }