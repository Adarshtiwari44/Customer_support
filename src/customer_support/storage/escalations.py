"""
Escalation storage layer - stores cases that need human review.
Simple in-memory storage for now, can be upgraded to SQLite/PostgreSQL later.
"""
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass, asdict
import json


@dataclass
class Escalation:
    """Single escalation case waiting for human review."""
    id: str
    timestamp: str
    customer_message: str
    draft_response: Optional[str]
    escalation_reason: str
    intent: Optional[str]
    confidence: Optional[float]
    confidence_tier: Optional[str]
    evidence_quality: Optional[str]
    status: str  # "PENDING", "APPROVED", "REJECTED", "SENT", "HUMAN_ACTIVE", "CLOSED"
    conversation_id: Optional[str] = None
    human_response: Optional[str] = None
    human_notes: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None


class EscalationStore:
    """In-memory escalation store with persistence to JSON file."""

    def __init__(self, persist_file: str = "escalations_queue.json"):
        self.escalations: Dict[str, Escalation] = {}
        self.persist_file = persist_file
        self._load()

    def _load(self):
        """Load from disk if exists."""
        try:
            with open(self.persist_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    esc = Escalation(**item)
                    self.escalations[esc.id] = esc
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[EscalationStore] Error loading persist file: {e}")

    def _save(self):
        """Persist to disk."""
        with open(self.persist_file, 'w', encoding='utf-8') as f:
            data = [asdict(e) for e in self.escalations.values()]
            json.dump(data, f, indent=2)

    def add(self, escalation: Escalation) -> None:
        """Add new escalation to queue."""
        self.escalations[escalation.id] = escalation
        self._save()

    def get(self, escalation_id: str) -> Optional[Escalation]:
        """Get escalation by ID."""
        return self.escalations.get(escalation_id)

    def get_pending(self) -> List[Escalation]:
        """Get all pending escalations (need human review)."""
        return [e for e in self.escalations.values() if e.status == "PENDING"]

    def approve(self, escalation_id: str, human_response: Optional[str] = None,
                agent_name: str = "human_agent") -> Optional[Escalation]:
        """Approve escalation (optionally with edited response)."""
        esc = self.escalations.get(escalation_id)
        if not esc:
            return None

        esc.status = "APPROVED"
        esc.human_response = human_response or esc.draft_response
        esc.resolved_at = datetime.utcnow().isoformat()
        esc.resolved_by = agent_name
        self._save()
        return esc

    def reject(self, escalation_id: str, human_response: str,
               notes: Optional[str] = None, agent_name: str = "human_agent") -> Optional[Escalation]:
        """Reject AI draft, use custom human response."""
        esc = self.escalations.get(escalation_id)
        if not esc:
            return None

        esc.status = "REJECTED"
        esc.human_response = human_response
        esc.human_notes = notes
        esc.resolved_at = datetime.utcnow().isoformat()
        esc.resolved_by = agent_name
        self._save()
        return esc

    def get_by_conversation_id(self, conversation_id: str) -> Optional[Escalation]:
        """Get escalation by conversation ID (latest first)."""
        matching = [e for e in self.escalations.values() if e.conversation_id == conversation_id]
        if matching:
            return sorted(matching, key=lambda x: x.timestamp, reverse=True)[0]
        return None

    def close(self, escalation_id: str, agent_name: str = "human_agent") -> Optional[Escalation]:
        """Close escalation and end human support."""
        esc = self.escalations.get(escalation_id)
        if not esc:
            return None
        esc.status = "CLOSED"
        esc.resolved_at = datetime.utcnow().isoformat()
        esc.resolved_by = agent_name
        self._save()
        return esc

    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        stats = {
            "total": len(self.escalations),
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "human_active": 0,
            "closed": 0,
        }
        for esc in self.escalations.values():
            if esc.status == "PENDING":
                stats["pending"] += 1
            elif esc.status == "APPROVED":
                stats["approved"] += 1
            elif esc.status == "REJECTED":
                stats["rejected"] += 1
            elif esc.status == "HUMAN_ACTIVE":
                stats["human_active"] += 1
            elif esc.status == "CLOSED":
                stats["closed"] += 1
        return stats


# Global store instance
_store = EscalationStore()


def get_store() -> EscalationStore:
    """Get the global escalation store."""
    return _store
