"""
Entity extraction and slot filling - extract information from messages
and track what's collected vs what's still needed.
"""
import re
from typing import Dict, List, Any

from customer_support.agent.state import AgentState


# Simple regex-based entity extraction (can be upgraded to NER later)
ORDER_ID_PATTERN = r'\b[A-Z0-9]{5,20}\b'
MARKETPLACE_PATTERN = r'amazon\.(com|co\.uk|de|fr|jp|ca|in)'
EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
PHONE_PATTERN = r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b'

# Define which entities are required for each intent
INTENT_REQUIRED_ENTITIES = {
    "delivery_status": ["order_id"],
    "order_issue": ["order_id"],
    "refund_return": ["order_id"],
    "payment_billing": ["order_id"],
    "repair_service_status": ["order_id"],
    "content_streaming_issue": [],
    "device_tech_support": [],
    "account_access": ["email"],
    "availability_question": [],
    "promo_discount_query": [],
    "feature_request": [],
    "product_issue": [],
    "pricing_query": [],
    "prime_membership": [],
    "customer_service_complaint": [],
    "human_assistance_request": [],
}


def extract_entities(state: AgentState) -> AgentState:
    """
    Extract entities from current message and update collected_entities.
    Determine what entities are still missing for current intent.
    """
    current_message = state.get("current_message", "")
    intent = state.get("intent", "UNKNOWN")
    collected = dict(state.get("collected_entities", {}))
    errors = list(state.get("errors", []))

    if not current_message:
        return {
            **state,
            "collected_entities": collected,
            "missing_entities": [],
        }

    # Extract order ID (common pattern: alphanumeric 5-20 chars)
    if "order_id" not in collected:
        match = re.search(ORDER_ID_PATTERN, current_message)
        if match:
            collected["order_id"] = match.group(0)

    # Extract marketplace
    if "marketplace" not in collected:
        match = re.search(MARKETPLACE_PATTERN, current_message.lower())
        if match:
            collected["marketplace"] = match.group(0)

    # Extract email
    if "email" not in collected:
        match = re.search(EMAIL_PATTERN, current_message)
        if match:
            collected["email"] = match.group(0)

    # Extract phone number
    if "phone" not in collected:
        match = re.search(PHONE_PATTERN, current_message)
        if match:
            collected["phone"] = "".join(match.groups())

    # Determine what's still needed for the current intent
    required = INTENT_REQUIRED_ENTITIES.get(intent, [])
    missing = [e for e in required if e not in collected]

    return {
        **state,
        "collected_entities": collected,
        "missing_entities": missing,
        "errors": errors,
    }
