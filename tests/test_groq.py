from customer_support.agent.validators import validate_response

# Test 1: Valid response (jaisa humne pichhle step me dekha)
state1 = {
    "draft_response": "We are sorry to hear your package has not arrived. Please check the status in your account.",
    "grounding_refs": ["EV-1187094"],
    "evidence": [{"evidence_id": "EV-1187094"}],
}
r1 = validate_response(state1)
print("Test 1 (valid):", r1["response_valid"])

# Test 2: Forbidden completion claim (should FAIL)
state2 = {
    "draft_response": "Your refund has been processed and will reflect in 3-5 days.",
    "grounding_refs": [],
    "evidence": [],
}
r2 = validate_response(state2)
print("Test 2 (forbidden claim):", r2["response_valid"], "| high_risk:", r2.get("high_risk"))

# Test 3: Hallucinated citation (should FAIL)
state3 = {
    "draft_response": "Based on similar cases, this should resolve soon.",
    "grounding_refs": ["EV-9999999"],  # ye evidence me nahi hai
    "evidence": [{"evidence_id": "EV-1187094"}],
}
r3 = validate_response(state3)
print("Test 3 (hallucinated ref):", r3["response_valid"], "| high_risk:", r3.get("high_risk"))

# Test 4: Empty response (should FAIL)
state4 = {"draft_response": None, "grounding_refs": [], "evidence": []}
r4 = validate_response(state4)
print("Test 4 (empty):", r4["response_valid"])