from typing import Optional, List, Dict, Any
from typing_extensions import TypedDict


class ConversationTurn(TypedDict):
    tweet_id: str
    author_id: str
    role: str  # "CUSTOMER" or "BRAND"
    text: str
    cleaned_text: str


class EvidenceItem(TypedDict):
    evidence_id: str
    conversation_id: str
    relevance_score: float
    resolution_text: str
    source_turns: List[ConversationTurn]


class AgentState(TypedDict, total=False):
    # ---- Input ----
    brand_id: str
    conversation_id: Optional[str]
    current_message: str
    context_turns: List[ConversationTurn]

    # ---- Context Builder output ----
    relevant_context: List[ConversationTurn]
    context_used: bool

    # ---- Intent Engine output ----
    intent: Optional[str]              # one of the 16 taxonomy labels, or "UNKNOWN"/"AMBIGUOUS"
    confidence: Optional[float]        # 0..1
    confidence_tier: Optional[str]     # "HIGH" / "MEDIUM" / "LOW"
    secondary_intents: List[str]

    # ---- Retrieval output ----
    evidence: List[EvidenceItem]
    evidence_quality: Optional[str]    # "STRONG" / "WEAK" / "CONTRADICTORY" / "NONE"

    # ---- Generation output ----
    draft_response: Optional[str]
    grounding_refs: List[str]
    claims: List[str]
    limitations: List[str]

    # ---- Validation / risk signals ----
    response_valid: Optional[bool]
    explicit_human_request: bool
    high_risk: bool
    contradictory_evidence: bool

    # ---- Routing decision ----
    decision: Optional[str]            # "AUTO_HANDLE", "NEED_INFORMATION", or "ESCALATE"
    escalation_reason: Optional[str]

    # ---- NEW: Persistent conversation state ----
    conversation_session: Optional[Dict[str, Any]]  # Full ConversationSession as dict
    current_intent: Optional[str]      # Intent from previous turns
    collected_entities: Dict[str, Any] # Slot filling: {"order_id": "12345", "marketplace": "amazon.com"}
    missing_entities: List[str]        # What info is still needed
    conversation_status: Optional[str] # "ACTIVE", "NEED_INFO", "ESCALATED", "RESOLVED"
    is_followup_answer: bool           # Is this answering a previous question?

    # ---- Metadata ----
    prediction_id: Optional[str]
    versions: Dict[str, str]
    errors: List[str]