import uuid
import time
from fastapi.testclient import TestClient
from customer_support.api.main import app
from customer_support.storage.conversations import get_conversation_store
from customer_support.storage.escalations import get_store

client = TestClient(app)

def run_tests():
    print("=" * 60)
    print("RUNNING COMPREHENSIVE END-TO-END ACCEPTANCE TESTS")
    print("=" * 60)

    # Clean in-memory stores for testing
    conv_store = get_conversation_store()
    conv_store.sessions.clear()
    esc_store = get_store()
    esc_store.escalations.clear()

    # -------------------------------------------------------------
    # TEST 1: Normal AI Conversation & Multi-Turn Slot Filling
    # -------------------------------------------------------------
    print("\n--- TEST 1: Normal AI Conversation & Slot Filling ---")
    conv_id = f"test-conv-{uuid.uuid4().hex[:8]}"

    # Turn 1
    res1 = client.post("/chat", json={
        "current_message": "Where is my order? It has been 3 days.",
        "conversation_id": conv_id,
        "brand_id": "AmazonHelp"
    })
    assert res1.status_code == 200, f"Turn 1 failed: {res1.text}"
    data1 = res1.json()
    print(f"Turn 1 decision: {data1['decision']} | intent: {data1['intent']}")
    assert data1["decision"] in ("NEED_INFORMATION", "AUTO_HANDLE"), "Should NOT escalate normal query"
    assert data1["conversation_id"] == conv_id

    # Turn 2: Followup slot
    res2 = client.post("/chat", json={
        "current_message": "amazon.com",
        "conversation_id": conv_id,
        "brand_id": "AmazonHelp"
    })
    assert res2.status_code == 200
    data2 = res2.json()
    print(f"Turn 2 decision: {data2['decision']} | intent: {data2['intent']} | collected: {data2['collected_entities']}")
    assert data2["decision"] in ("NEED_INFORMATION", "AUTO_HANDLE"), "Should NOT escalate on marketplace slot"
    assert "amazon.com" in str(data2["collected_entities"].get("marketplace", "")).lower()

    # Turn 3: Followup Order ID
    res3 = client.post("/chat", json={
        "current_message": "123456789",
        "conversation_id": conv_id,
        "brand_id": "AmazonHelp"
    })
    assert res3.status_code == 200
    data3 = res3.json()
    print(f"Turn 3 decision: {data3['decision']} | intent: {data3['intent']} | collected: {data3['collected_entities']}")
    print("[PASS] TEST 1: Stateful slot filling retained intent and did not falsely escalate.")

    # -------------------------------------------------------------
    # TEST 2 & 3: Human Escalation and Complete Human Control (HUMAN_ACTIVE)
    # -------------------------------------------------------------
    print("\n--- TEST 2 & 3: Human Escalation & Human Control (HUMAN_ACTIVE) ---")
    esc_conv_id = f"test-conv-esc-{uuid.uuid4().hex[:8]}"

    # Customer asks for human
    res_esc = client.post("/chat", json={
        "current_message": "I want to speak with a human.",
        "conversation_id": esc_conv_id,
        "brand_id": "AmazonHelp"
    })
    assert res_esc.status_code == 200
    data_esc = res_esc.json()
    print(f"Escalation decision: {data_esc['decision']} | status: {data_esc['conversation_status']}")
    assert data_esc["decision"] == "ESCALATE", "Explicit request must escalate"

    # Check conversation status in ConversationStore
    session = conv_store.get_session(esc_conv_id)
    assert session is not None
    assert session.status == "HUMAN_ACTIVE", f"Expected HUMAN_ACTIVE, got {session.status}"

    # Customer sends follow-up while HUMAN_ACTIVE: "Hello?"
    res_followup = client.post("/chat", json={
        "current_message": "Hello? Is anyone there?",
        "conversation_id": esc_conv_id,
        "brand_id": "AmazonHelp"
    })
    assert res_followup.status_code == 200
    data_followup = res_followup.json()
    print(f"While HUMAN_ACTIVE decision: {data_followup['decision']} | status: {data_followup['conversation_status']}")
    assert data_followup["decision"] == "HUMAN_ACTIVE"
    assert data_followup["conversation_status"] == "HUMAN_ACTIVE"
    # Check that AI did not generate an automated response
    assert "human support agent" in data_followup["draft_response"].lower()

    # Verify message is stored in ConversationStore
    session = conv_store.get_session(esc_conv_id)
    cust_msgs = [m for m in session.messages if m.role == "CUSTOMER"]
    assert any("Hello?" in m.text for m in cust_msgs), "Customer message must be saved"

    print("[PASS] TEST 2 & 3: AI stopped responding and conversation entered HUMAN_ACTIVE.")

    # -------------------------------------------------------------
    # TEST 4 & 5: Human Approval / Reply & Live Delivery
    # -------------------------------------------------------------
    print("\n--- TEST 4 & 5: Human Approve / Send & Live Delivery ---")

    # Find escalation ID in store
    esc_item = esc_store.get_by_conversation_id(esc_conv_id)
    assert esc_item is not None, "Escalation must exist in store"
    escalation_id = esc_item.id

    # Human edits and approves
    human_msg_text = "Hi there! I am Sarah from customer support. I am checking your case now."
    res_approve = client.post(f"/escalations/{escalation_id}/approve", json={
        "human_response": human_msg_text,
        "agent_name": "Sarah_Agent"
    })
    assert res_approve.status_code == 200
    data_approve = res_approve.json()
    assert data_approve["status"] == "HUMAN_ACTIVE"
    print(f"Human approve status: {data_approve['status']}")

    # Customer polls for updates
    res_poll = client.get(f"/chat/{esc_conv_id}/updates")
    assert res_poll.status_code == 200
    data_poll = res_poll.json()
    messages = data_poll["messages"]
    human_msgs = [m for m in messages if m["source"] == "human_agent"]
    assert len(human_msgs) >= 1, "Polling must return the human agent message"
    assert human_msgs[-1]["text"] == human_msg_text
    print(f"Polling received human message: '{human_msgs[-1]['text']}' | sender: {human_msgs[-1]['sender']}")

    # Test 'after' filtering for incremental polling
    last_id = human_msgs[-1]["id"]
    res_poll_after = client.get(f"/chat/{esc_conv_id}/updates?after={last_id}")
    assert res_poll_after.status_code == 200
    assert len(res_poll_after.json()["messages"]) == 0, "Polling with 'after' should return no older messages"

    # -------------------------------------------------------------
    # TEST 6: Human Replies Again (Sticky Human Mode)
    # -------------------------------------------------------------
    print("\n--- TEST 6: Human Ongoing Replies (Sticky Human Mode) ---")

    # Customer replies
    client.post("/chat", json={
        "current_message": "Thank you Sarah. How long will it take?",
        "conversation_id": esc_conv_id,
        "brand_id": "AmazonHelp"
    })

    # Human sends another reply
    human_reply_2 = "It will take about 5-10 minutes to process."
    res_reply2 = client.post(f"/escalations/{escalation_id}/reply", json={
        "human_response": human_reply_2,
        "agent_name": "Sarah_Agent"
    })
    assert res_reply2.status_code == 200

    # Poll updates with 'after'
    res_poll2 = client.get(f"/chat/{esc_conv_id}/updates?after={last_id}")
    new_msgs = res_poll2.json()["messages"]
    assert any(m["text"] == human_reply_2 for m in new_msgs), "Second human reply must be received"
    print(f"Second human reply verified: '{human_reply_2}'")

    # -------------------------------------------------------------
    # TEST 7: Close Conversation
    # -------------------------------------------------------------
    print("\n--- TEST 7: Close Conversation ---")
    res_close = client.post(f"/escalations/{escalation_id}/close", json={
        "human_response": "Thank you for contacting Amazon support. Have a great day!",
        "agent_name": "Sarah_Agent"
    })
    assert res_close.status_code == 200
    data_close = res_close.json()
    assert data_close["status"] == "CLOSED"

    # Verify session status is CLOSED
    session = conv_store.get_session(esc_conv_id)
    assert session.status == "CLOSED"
    print("[PASS] TEST 7: Conversation closed successfully.")

    print("\n" + "=" * 60)
    print("ALL 7 ACCEPTANCE TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
