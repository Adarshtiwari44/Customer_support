import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from customer_support.agent.graph import app as agent_app
from customer_support.agent.state import ConversationTurn
from customer_support.storage.escalations import get_store, Escalation
from customer_support.storage.conversations import (
    get_conversation_store,
    ConversationMessage,
)

# ---- Logging ----
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base directory for frontend static files
BASE_DIR = Path(__file__).resolve().parents[3]
FRONTEND_DIR = BASE_DIR / "frontend"

# ---- FastAPI app ----
app = FastAPI(
    title="Customer Support AI Agent",
    description="Amazon-style customer support agent - stateful multi-turn conversation, slot-filling, grounded responses, and smart escalation.",
    version="0.2.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Request / Response schemas ----

class EscalationAction(BaseModel):
    """Action taken by human agent on an escalation."""
    human_response: Optional[str] = None
    notes: Optional[str] = None
    agent_name: str = "human_agent"


class ContextTurn(BaseModel):
    """Single conversation turn."""
    tweet_id: str = ""
    author_id: str = ""
    role: str = "CUSTOMER"  # "CUSTOMER" or "BRAND"
    text: str = ""
    cleaned_text: str = ""


class ChatRequest(BaseModel):
    """Client request with current message and conversation ID."""
    current_message: str = Field(..., min_length=1, description="Customer current message")
    brand_id: str = Field(default="AmazonHelp", description="Brand identifier")
    conversation_id: Optional[str] = Field(default=None, description="Persistent conversation ID")
    context_turns: List[ContextTurn] = Field(default_factory=list, description="Recent conversation turns")


class ChatResponse(BaseModel):
    """Agent pipeline response."""
    prediction_id: str
    conversation_id: str
    decision: str                       # "AUTO_HANDLE", "NEED_INFORMATION", or "ESCALATE"
    escalation_reason: Optional[str]

    # Draft response
    draft_response: Optional[str]
    claims: List[str]
    limitations: List[str]
    grounding_refs: List[str]

    # Classification & state info
    intent: Optional[str]
    confidence: Optional[float]
    confidence_tier: Optional[str]
    collected_entities: Dict[str, Any] = Field(default_factory=dict)
    missing_entities: List[str] = Field(default_factory=list)
    conversation_status: Optional[str] = "ACTIVE"

    # Evidence info
    evidence_quality: Optional[str]

    # Safety flags
    response_valid: Optional[bool]
    high_risk: bool
    explicit_human_request: bool

    # Pipeline errors
    errors: List[str]


# ---- Routes ----

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Main chat endpoint: stateful pipeline processing.
    Checks if conversation is HUMAN_ACTIVE and routes accordingly.
    """
    prediction_id = f"pred-{uuid.uuid4().hex[:12]}"
    conversation_id = request.conversation_id or f"conv-{uuid.uuid4().hex[:12]}"

    logger.info(f"[CHAT] conversation_id={conversation_id} | message={request.current_message[:80]}...")

    # Check if conversation is in HUMAN_ACTIVE state
    conv_store = get_conversation_store()
    session = conv_store.get_session(conversation_id)

    if session and session.status == "HUMAN_ACTIVE":
        # Store customer message but DO NOT run AI pipeline
        logger.info(f"[CHAT] conversation_id={conversation_id} is HUMAN_ACTIVE - storing message, NOT running AI")

        conv_store.add_message(
            conversation_id,
            ConversationMessage(
                id=f"msg-{uuid.uuid4().hex[:8]}",
                conversation_id=conversation_id,
                role="CUSTOMER",
                text=request.current_message,
                timestamp=datetime.utcnow().isoformat(),
                source="customer",
            ),
        )

        # Return human takeover response
        return ChatResponse(
            prediction_id=prediction_id,
            conversation_id=conversation_id,
            decision="HUMAN_ACTIVE",
            escalation_reason="Conversation is currently being handled by a human support agent",
            draft_response="Your message has been received. A human support agent is assisting you and will respond shortly.",
            claims=[],
            limitations=["conversation under human control"],
            grounding_refs=[],
            intent=session.current_intent,
            confidence=1.0,
            confidence_tier="HIGH",
            collected_entities=session.collected_entities,
            missing_entities=[],
            conversation_status="HUMAN_ACTIVE",
            evidence_quality="N/A",
            response_valid=True,
            high_risk=False,
            explicit_human_request=False,
            errors=[],
        )

    # Normal AI pipeline processing
    context_turns: List[ConversationTurn] = [
        {
            "tweet_id": turn.tweet_id,
            "author_id": turn.author_id,
            "role": turn.role,
            "text": turn.text,
            "cleaned_text": turn.cleaned_text or turn.text,
        }
        for turn in request.context_turns
    ]

    initial_state = {
        "brand_id": request.brand_id,
        "conversation_id": conversation_id,
        "current_message": request.current_message,
        "context_turns": context_turns,
        "prediction_id": prediction_id,
        "errors": [],
    }

    try:
        result = agent_app.invoke(initial_state)
    except Exception as e:
        logger.error(f"[{prediction_id}] Pipeline failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Agent pipeline failed: {type(e).__name__}",
        )

    decision = result.get("decision", "AUTO_HANDLE")
    logger.info(f"[{conversation_id}] Decision: {decision} | Intent: {result.get('intent')}")

    # If ESCALATE, add to human review queue and set conversation to HUMAN_ACTIVE
    if decision == "ESCALATE":
        store = get_store()
        escalation = Escalation(
            id=prediction_id,
            timestamp=datetime.utcnow().isoformat(),
            conversation_id=conversation_id,
            customer_message=request.current_message,
            draft_response=result.get("draft_response"),
            escalation_reason=result.get("escalation_reason") or "Requires human review",
            intent=result.get("intent"),
            confidence=result.get("confidence"),
            confidence_tier=result.get("confidence_tier"),
            evidence_quality=result.get("evidence_quality"),
            status="PENDING",
        )
        store.add(escalation)

        # Set conversation to HUMAN_ACTIVE immediately
        conv_store.update_session(
            conversation_id,
            {"status": "HUMAN_ACTIVE", "escalation_id": prediction_id}
        )
        logger.info(f"[{prediction_id}] ESCALATED -> conversation {conversation_id} now HUMAN_ACTIVE")

    return ChatResponse(
        prediction_id=prediction_id,
        conversation_id=conversation_id,
        decision=decision,
        escalation_reason=result.get("escalation_reason"),
        draft_response=result.get("draft_response"),
        claims=result.get("claims", []),
        limitations=result.get("limitations", []),
        grounding_refs=result.get("grounding_refs", []),
        intent=result.get("intent"),
        confidence=result.get("confidence"),
        confidence_tier=result.get("confidence_tier"),
        collected_entities=result.get("collected_entities", {}),
        missing_entities=result.get("missing_entities", []),
        conversation_status=result.get("conversation_status", "ACTIVE"),
        evidence_quality=result.get("evidence_quality"),
        response_valid=result.get("response_valid"),
        high_risk=result.get("high_risk", False),
        explicit_human_request=result.get("explicit_human_request", False),
        errors=result.get("errors", []),
    )


@app.get("/chat/{conversation_id}/updates")
def get_conversation_updates(
    conversation_id: str,
    since: Optional[str] = None,
    after: Optional[str] = None,
):
    """
    Poll for updates/new messages in a conversation.
    Enables live delivery of human-approved responses.
    Supports filtering by 'since' timestamp or 'after' message_id.
    """
    store = get_conversation_store()
    session = store.get_session(conversation_id)

    if not session:
        return {"conversation_id": conversation_id, "messages": [], "status": "ACTIVE"}

    messages = session.messages

    if after:
        # Find index of message with id == after, and take subsequent messages
        found_idx = -1
        for idx, m in enumerate(messages):
            if m.id == after:
                found_idx = idx
                break
        if found_idx != -1:
            messages = messages[found_idx + 1 :]

    if since:
        messages = [m for m in messages if m.timestamp > since]

    if messages:
        logger.info(f"[POLL] conversation_id={conversation_id} | new_messages={len(messages)}")

    return {
        "conversation_id": conversation_id,
        "status": session.status,
        "current_intent": session.current_intent,
        "collected_entities": session.collected_entities,
        "messages": [
            {
                "id": m.id,
                "conversation_id": m.conversation_id,
                "role": m.role,
                "text": m.text,
                "timestamp": m.timestamp,
                "source": m.source,
                "sender": "human" if m.source == "human_agent" else ("customer" if m.role == "CUSTOMER" else "ai"),
                "message_type": "human_response" if m.source == "human_agent" else "chat_message",
            }
            for m in messages
        ],
    }


@app.post("/escalations/{escalation_id}/reply")
def reply_escalation(escalation_id: str, action: EscalationAction):
    """
    Human agent sends an ongoing reply in HUMAN_ACTIVE mode.
    """
    if not action.human_response:
        raise HTTPException(status_code=400, detail="human_response is required")

    store = get_store()
    esc = store.get(escalation_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")

    esc.status = "HUMAN_ACTIVE"
    esc.human_response = action.human_response
    esc.resolved_by = action.agent_name
    store._save()

    if esc.conversation_id:
        conv_store = get_conversation_store()
        msg_id = f"msg-{uuid.uuid4().hex[:8]}"
        msg_timestamp = datetime.utcnow().isoformat()

        conv_store.add_message(
            esc.conversation_id,
            ConversationMessage(
                id=msg_id,
                conversation_id=esc.conversation_id,
                role="BRAND",
                text=action.human_response,
                timestamp=msg_timestamp,
                source="human_agent",
            ),
        )

        conv_store.update_session(
            esc.conversation_id,
            {
                "status": "HUMAN_ACTIVE",
                "updated_at": msg_timestamp
            },
        )

        logger.info(f"[HUMAN] escalation_id={escalation_id} REPLY -> conversation_id={esc.conversation_id} | msg_id={msg_id}")

    return {
        "status": "HUMAN_ACTIVE",
        "message": "Reply sent to customer",
        "final_response": action.human_response,
        "conversation_id": esc.conversation_id,
    }


@app.post("/escalations/{escalation_id}/close")
def close_escalation(escalation_id: str, action: EscalationAction = None):
    """
    Human agent closes conversation / ends human support.
    Transitions conversation to CLOSED state.
    """
    store = get_store()
    agent_name = action.agent_name if action else "human_agent"
    esc = store.close(escalation_id, agent_name=agent_name)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")

    if esc.conversation_id:
        conv_store = get_conversation_store()
        msg_id = f"msg-{uuid.uuid4().hex[:8]}"
        msg_timestamp = datetime.utcnow().isoformat()

        # Add closing message from human agent
        closing_text = (action.human_response if action and action.human_response else "This support session has been closed by the agent. Thank you for contacting us.")

        conv_store.add_message(
            esc.conversation_id,
            ConversationMessage(
                id=msg_id,
                conversation_id=esc.conversation_id,
                role="BRAND",
                text=closing_text,
                timestamp=msg_timestamp,
                source="human_agent",
            ),
        )

        conv_store.update_session(
            esc.conversation_id,
            {
                "status": "CLOSED",
                "updated_at": msg_timestamp,
            },
        )

        logger.info(f"[HUMAN] escalation_id={escalation_id} CLOSED -> conversation_id={esc.conversation_id} | status=CLOSED")

    return {
        "status": "CLOSED",
        "message": "Conversation closed and marked as resolved",
        "conversation_id": esc.conversation_id,
    }


# ---- Escalation Queue Endpoints (Human-in-the-Loop) ----

@app.get("/escalations")
def get_escalations(status: Optional[str] = "PENDING"):
    """
    Get escalations from queue.
    Retrieves latest customer message from conversation session if available.
    """
    store = get_store()
    conv_store = get_conversation_store()

    if status == "PENDING":
        escalations = store.get_pending()
    else:
        escalations = list(store.escalations.values())
        if status:
            escalations = [e for e in escalations if e.status == status]

    result_escalations = []
    for e in escalations:
        latest_customer_message = e.customer_message
        if e.conversation_id:
            session = conv_store.get_session(e.conversation_id)
            if session:
                # Find the most recent customer message
                customer_msgs = [m for m in session.messages if m.role == "CUSTOMER"]
                if customer_msgs:
                    latest_customer_message = customer_msgs[-1].text

        result_escalations.append({
            "id": e.id,
            "conversation_id": e.conversation_id,
            "timestamp": e.timestamp,
            "customer_message": latest_customer_message,
            "draft_response": e.draft_response,
            "escalation_reason": e.escalation_reason,
            "intent": e.intent,
            "confidence": e.confidence,
            "confidence_tier": e.confidence_tier,
            "evidence_quality": e.evidence_quality,
            "status": e.status,
            "human_response": e.human_response,
            "human_notes": e.human_notes,
            "resolved_at": e.resolved_at,
            "resolved_by": e.resolved_by,
        })

    return {
        "stats": store.get_stats(),
        "count": len(result_escalations),
        "escalations": result_escalations,
    }


@app.get("/escalations/{escalation_id}")
def get_escalation(escalation_id: str):
    """Get single escalation details."""
    store = get_store()
    esc = store.get(escalation_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return esc


@app.post("/escalations/{escalation_id}/approve")
def approve_escalation(escalation_id: str, action: EscalationAction):
    """
    Human agent APPROVES the escalation.
    Delivers the approved response directly into the conversation.
    Sets escalation status to HUMAN_ACTIVE (not APPROVED).
    """
    store = get_store()
    esc = store.get(escalation_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")

    # Update escalation to HUMAN_ACTIVE
    esc.status = "HUMAN_ACTIVE"
    esc.human_response = action.human_response or esc.draft_response
    esc.resolved_by = action.agent_name
    store._save()

    # Deliver response to conversation
    if esc.conversation_id:
        conv_store = get_conversation_store()
        final_text = action.human_response or esc.draft_response or "Our support team is here to help you."

        msg_id = f"msg-{uuid.uuid4().hex[:8]}"
        msg_timestamp = datetime.utcnow().isoformat()

        conv_store.add_message(
            esc.conversation_id,
            ConversationMessage(
                id=msg_id,
                conversation_id=esc.conversation_id,
                role="BRAND",
                text=final_text,
                timestamp=msg_timestamp,
                source="human_agent",
            ),
        )

        # Keep conversation in HUMAN_ACTIVE state
        conv_store.update_session(
            esc.conversation_id,
            {
                "status": "HUMAN_ACTIVE",
                "updated_at": msg_timestamp
            },
        )

        logger.info(f"[HUMAN] escalation_id={escalation_id} APPROVED -> conversation_id={esc.conversation_id} | status=HUMAN_ACTIVE | msg_id={msg_id}")

    return {
        "status": "HUMAN_ACTIVE",
        "message": "Response delivered to live customer chat. Human support is now active.",
        "final_response": esc.human_response,
        "conversation_id": esc.conversation_id,
    }


@app.post("/escalations/{escalation_id}/reject")
def reject_escalation(escalation_id: str, action: EscalationAction):
    """
    Human agent REJECTS the AI draft and writes a custom response.
    Delivers custom response directly into the conversation.
    Sets escalation status to HUMAN_ACTIVE (not REJECTED).
    """
    if not action.human_response:
        raise HTTPException(
            status_code=400,
            detail="human_response is required when rejecting AI draft",
        )

    store = get_store()
    esc = store.get(escalation_id)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")

    # Update escalation to HUMAN_ACTIVE
    esc.status = "HUMAN_ACTIVE"
    esc.human_response = action.human_response
    esc.human_notes = action.notes
    esc.resolved_by = action.agent_name
    store._save()

    # Deliver custom response to conversation
    if esc.conversation_id:
        conv_store = get_conversation_store()

        msg_id = f"msg-{uuid.uuid4().hex[:8]}"
        msg_timestamp = datetime.utcnow().isoformat()

        conv_store.add_message(
            esc.conversation_id,
            ConversationMessage(
                id=msg_id,
                conversation_id=esc.conversation_id,
                role="BRAND",
                text=action.human_response,
                timestamp=msg_timestamp,
                source="human_agent",
            ),
        )

        # Keep conversation in HUMAN_ACTIVE state
        conv_store.update_session(
            esc.conversation_id,
            {
                "status": "HUMAN_ACTIVE",
                "updated_at": msg_timestamp
            },
        )

        logger.info(f"[HUMAN] escalation_id={escalation_id} CUSTOM RESPONSE -> conversation_id={esc.conversation_id} | status=HUMAN_ACTIVE | msg_id={msg_id}")

    return {
        "status": "HUMAN_ACTIVE",
        "message": "Custom response delivered to live customer chat. Human support is now active.",
        "final_response": esc.human_response,
        "conversation_id": esc.conversation_id,
    }


# ---- Static files (Frontend) ----
@app.get("/")
def serve_frontend():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Frontend not found, access API at /docs"}


@app.get("/review")
def serve_review():
    review_file = FRONTEND_DIR / "review.html"
    if review_file.exists():
        return FileResponse(review_file)
    return {"message": "Review dashboard not found"}


@app.get("/support")
def serve_support():
    support_file = FRONTEND_DIR / "support.html"
    if support_file.exists():
        return FileResponse(support_file)
    return {"message": "Support dashboard not found"}


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
