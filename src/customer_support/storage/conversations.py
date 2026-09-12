"""
Conversation storage layer - persists multi-turn conversation sessions,
message histories, collected slots/entities, and current intents.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict, field
import json
import os
from pathlib import Path


@dataclass
class ConversationMessage:
    """Single message in a conversation."""
    id: str
    conversation_id: str
    role: str  # "CUSTOMER" or "BRAND"
    text: str
    timestamp: str
    intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    source: str = "ai"  # "ai", "customer", "human_agent"


@dataclass
class ConversationSession:
    """Persistent state of a conversation across multiple turns."""
    id: str
    created_at: str
    updated_at: str
    current_intent: Optional[str] = None
    collected_entities: Dict[str, Any] = field(default_factory=dict)
    missing_entities: List[str] = field(default_factory=list)
    status: str = "ACTIVE"  # "ACTIVE", "NEED_INFO", "ESCALATED", "HUMAN_ACTIVE", "CLOSED"
    messages: List[ConversationMessage] = field(default_factory=list)
    escalation_id: Optional[str] = None
    summary: Optional[str] = None


class ConversationStore:
    """In-memory conversation store with JSON persistence."""

    def __init__(self, persist_file: str = "conversations.json"):
        self.persist_file = persist_file
        self.sessions: Dict[str, ConversationSession] = {}
        self._load()

    def _load(self):
        """Load conversations from disk if available."""
        if not os.path.exists(self.persist_file):
            return
        try:
            with open(self.persist_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    messages = [
                        ConversationMessage(**m) for m in item.get("messages", [])
                    ]
                    session = ConversationSession(
                        id=item["id"],
                        created_at=item["created_at"],
                        updated_at=item["updated_at"],
                        current_intent=item.get("current_intent"),
                        collected_entities=item.get("collected_entities", {}),
                        missing_entities=item.get("missing_entities", []),
                        status=item.get("status", "ACTIVE"),
                        messages=messages,
                        escalation_id=item.get("escalation_id"),
                        summary=item.get("summary"),
                    )
                    self.sessions[session.id] = session
        except Exception as e:
            # Fallback gracefully if file corrupted
            print(f"[ConversationStore] Error loading persist file: {e}")

    def _save(self):
        """Persist conversations to disk."""
        try:
            data = []
            for session in self.sessions.values():
                session_dict = asdict(session)
                data.append(session_dict)
            with open(self.persist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[ConversationStore] Error saving persist file: {e}")

    def get_or_create(self, conversation_id: str) -> ConversationSession:
        """Get existing conversation session or create a new one."""
        if conversation_id in self.sessions:
            return self.sessions[conversation_id]

        now = datetime.utcnow().isoformat()
        session = ConversationSession(
            id=conversation_id,
            created_at=now,
            updated_at=now,
            current_intent=None,
            collected_entities={},
            missing_entities=[],
            status="ACTIVE",
            messages=[],
        )
        self.sessions[conversation_id] = session
        self._save()
        return session

    def get_session(self, conversation_id: str) -> Optional[ConversationSession]:
        """Get conversation session by ID."""
        return self.sessions.get(conversation_id)

    def add_message(self, conversation_id: str, message: ConversationMessage) -> None:
        """Add a message to a conversation."""
        session = self.get_or_create(conversation_id)
        # Avoid duplicate message IDs
        if not any(m.id == message.id for m in session.messages):
            session.messages.append(message)
            session.updated_at = datetime.utcnow().isoformat()
            self._save()

    def update_session(self, conversation_id: str, updates: Dict[str, Any]) -> Optional[ConversationSession]:
        """Update session attributes."""
        session = self.get_or_create(conversation_id)
        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)
        session.updated_at = datetime.utcnow().isoformat()
        self._save()
        return session


# Global store instance
_conversation_store = ConversationStore()


def get_conversation_store() -> ConversationStore:
    """Get the global conversation store."""
    return _conversation_store
