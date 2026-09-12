"""
Conversation memory management - load/save conversation state across turns.
"""
import uuid
from datetime import datetime
from dataclasses import asdict
from typing import Dict, Any

from customer_support.storage.conversations import (
    get_conversation_store,
    ConversationMessage,
)
from customer_support.agent.state import AgentState


def load_conversation_memory(state: AgentState) -> AgentState:
    """
    Load persistent conversation state from storage.
    This runs BEFORE classification so we have context about the conversation.
    """
    conversation_id = state.get("conversation_id")

    if not conversation_id:
        # Generate new conversation_id if missing
        conversation_id = f"conv-{uuid.uuid4().hex[:12]}"

    store = get_conversation_store()
    session = store.get_or_create(conversation_id)

    # Load persistent state into AgentState
    return {
        **state,
        "conversation_id": conversation_id,
        "conversation_session": asdict(session),
        "current_intent": session.current_intent,
        "collected_entities": dict(session.collected_entities),
        "missing_entities": list(session.missing_entities),
        "conversation_status": session.status,
    }


def save_conversation_memory(state: AgentState) -> AgentState:
    """
    Save updated conversation state back to storage.
    This runs AFTER routing decision to persist the conversation.
    """
    conversation_id = state.get("conversation_id")
    if not conversation_id:
        return state

    store = get_conversation_store()

    # Add customer message to conversation history
    customer_msg_id = f"msg-{uuid.uuid4().hex[:8]}"
    store.add_message(
        conversation_id,
        ConversationMessage(
            id=customer_msg_id,
            conversation_id=conversation_id,
            role="CUSTOMER",
            text=state.get("current_message", ""),
            timestamp=datetime.utcnow().isoformat(),
            intent=state.get("intent"),
            entities=state.get("collected_entities"),
            source="customer",
        ),
    )

    # Add AI response if generated (and not escalated)
    draft_response = state.get("draft_response")
    decision = state.get("decision")
    if draft_response and decision != "ESCALATE":
        ai_msg_id = f"msg-{uuid.uuid4().hex[:8]}"
        store.add_message(
            conversation_id,
            ConversationMessage(
                id=ai_msg_id,
                conversation_id=conversation_id,
                role="BRAND",
                text=draft_response,
                timestamp=datetime.utcnow().isoformat(),
                source="ai",
            ),
        )

    # Update session state
    updates: Dict[str, Any] = {
        "current_intent": state.get("intent"),
        "collected_entities": state.get("collected_entities", {}),
        "missing_entities": state.get("missing_entities", []),
        "status": state.get("conversation_status", "ACTIVE"),
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Link escalation if escalated
    if decision == "ESCALATE" and state.get("prediction_id"):
        updates["escalation_id"] = state.get("prediction_id")

    store.update_session(conversation_id, updates)

    return state
