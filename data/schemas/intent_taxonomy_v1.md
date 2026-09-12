# Intent Taxonomy v1 — AmazonHelp (Customer Support AI Agent)

Derived from exploratory analysis of 60,669 clean English customer-support 
conversations (AmazonHelp brand, Customer Support on Twitter dataset).
Taxonomy version: v1 | Frozen before golden-set labelling.

---

## 1. delivery_status
**Definition:** Customer asks about the current location, tracking status, or 
expected/actual arrival of a package that has been shipped, where the primary 
need is status information (not a resolution action like refund/replacement).
**Positive examples:**
- "Where is my package? It should have arrived yesterday."
- "and since then no information. No texts or calls on it's status."
**Boundary:** If the customer explicitly wants a refund/replacement because 
delivery failed, classify as `order_issue` instead — the resolution ask 
dominates over the status question.

## 2. order_issue
**Definition:** Customer reports a problem with the order itself — wrong item 
received, item missing/never arrived (as a resolution complaint, not just a 
status check), or wants to cancel an order.
**Positive examples:**
- "Recvd a [X] headphone instead a sony BT hdph."
- "I spent 2+ hrs looking for a 400-page book I ordered in May & it's nowhere."
**Boundary:** Overlaps with `delivery_status` — key difference is whether the 
customer wants an outcome (replacement/refund/cancel) vs. just wants to know 
where the package is.

## 3. refund_return
**Definition:** Customer explicitly requests a refund, return, exchange, or 
reports a refund/cashback that hasn't been processed.
**Positive examples:**
- "22 din se sirf sorry bola ja raha hai lekin mera refund nahi hua."
- "You guys made me wait for such a long time, assured me of cashback."
**Boundary:** If refund is mentioned only as a hypothetical consequence of 
another issue (e.g. "if this isn't fixed I want a refund"), classify by the 
underlying issue first; escalate refund handling separately if it becomes the 
dominant ask.

## 4. payment_billing
**Definition:** Customer reports being charged incorrectly, double-charged, 
or has a question/dispute about a payment/billing transaction.
**Positive examples:**
- (charge/payment dispute pattern messages)
**Boundary:** Distinct from `pricing_query` — this is about an actual 
transaction/charge that occurred, not a general price question.

## 5. pricing_query
**Definition:** Customer questions a listed price, MRP mismatch, or 
overcharging on the product listing itself (pre-purchase or general question).
**Positive examples:**
- "MRP Rs. 99. Selling at Rs. 100?"
**Boundary:** If money has already been charged and is in dispute, use 
`payment_billing` instead.

## 6. prime_membership
**Definition:** Customer has a question, issue, or complaint specifically 
about their Prime subscription/membership (not Prime Video content).
**Positive examples:**
- "die von mir als „Prime" erworbene Lieferung „Next business day" gibt es 
  jetzt gar nicht mehr?"
**Boundary:** If the issue is about streaming content within Prime Video, use 
`content_streaming_issue` instead.

## 7. content_streaming_issue
**Definition:** Customer reports a problem with digital content — Prime 
Video, Audible, Kindle books — such as missing episodes, subtitle errors, 
region/geo restrictions, or empty library.
**Positive examples:**
- "it says audible library is empty even though books are there."
- "subtitles for Rizzoli and Isles are all messed up."
- "what happened to the 5th episode of lethal weapon S2"
**Boundary:** Distinct from `device_tech_support` — this is about content 
availability/quality, not a hardware/app connectivity problem.

## 8. device_tech_support
**Definition:** Customer needs help setting up, connecting, or troubleshooting 
an Amazon device (Echo, Alexa, Kindle device/app, controller, etc.).
**Positive examples:**
- "both my echos are no longer responding to voice commands.. bad update??"
- "trying to connect echo dot to wifi... does it not support to reliance jiofi"
**Boundary:** If the complaint is about digital content playing on the device 
rather than the device/connectivity itself, use `content_streaming_issue`.

## 9. repair_service_status
**Definition:** Customer is asking about the status of a physical product 
sent for repair/service (distinct from a delivery-in-transit package).
**Positive examples:**
- "I had purchased H6xon 11th July it showed battery prob on Sep, submitted 
  my mobile on BBSR SrvCentr 25th Sept, not yet rcvd"
**Boundary:** If the product was never received in the first place (never 
delivered), use `delivery_status` or `order_issue`, not this category.

## 10. account_access
**Definition:** Customer cannot log in, access their account, or needs help 
with account credentials/settings.
**Positive examples:**
- (login/password/account-lock pattern messages)
**Boundary:** N/A — fairly distinct category.

## 11. availability_question
**Definition:** Customer asks when a product/feature/service will become 
available, especially in their region.
**Positive examples:**
- "when would this be available in Amazon India??"
**Boundary:** If asking about delivery of an already-placed order, use 
`delivery_status` instead — this category is pre-purchase/general availability.

## 12. promo_discount_query
**Definition:** Customer asks about or reports an issue with a promo code, 
discount, coupon, or cashback offer not applying correctly.
**Positive examples:**
- "looking for a first time user promo code!"
- "I didn't get $5 off when I follow the steps"
**Boundary:** If the discount issue has escalated into a charged-incorrectly 
dispute, use `payment_billing`.

## 13. feature_request
**Definition:** Customer suggests a new feature or improvement; not reporting 
a problem or asking for support with an existing issue.
**Positive examples:**
- "it'd be cool if we had the option to have alarms or timers apply to all 
  the Echo devices in an audio group."
**Boundary:** Not a complaint — no resolution/action expected, generally low 
priority and safe to acknowledge without escalation.

## 14. product_issue
**Definition:** Customer reports a received product is damaged, defective, 
or not working as expected (distinct from repair-center tracking).
**Positive examples:**
- (damaged/defective/faulty pattern messages)
**Boundary:** If item is already sent for repair and question is about status, 
use `repair_service_status`.

## 15. customer_service_complaint
**Definition:** Customer expresses dissatisfaction with the support 
experience itself (rude agents, long wait times, unhelpful responses) rather 
than the underlying product/order issue.
**Positive examples:**
- "Congrats 2 of your chat agents managed to waste 2.5hrs of my time tonight"
- "No courtesy unhelpful agents..."
**Boundary:** Often layered on top of another intent — if a clear underlying 
issue (e.g. delivery) is also present, that takes priority as the primary 
intent; this category is for when the complaint IS the issue.

## 16. human_assistance_request
**Definition:** Customer explicitly asks to speak with a human/real person, 
or asks to stop automated replies.
**Positive examples:**
- "Stop sending me automated replies. I want a real person."
**Boundary:** Per PRD, this MUST route to ESCALATE regardless of other 
signals — it's a routing override, not just a classification label.

## UNKNOWN / AMBIGUOUS
**Definition:** Message has no clear identifiable support need, is vague 
venting without actionable content, is sarcastic without clear meaning, or is 
support-adjacent noise (e.g. promotional/unrelated tweets that mention the 
brand but aren't support requests).
**Positive examples:**
- "Will you or your company ever respond to my cry for help?"
- "Yo this your idea of a joke?"
**Boundary:** Do NOT force these into another category. Per PRD §13, rare/
unclear behaviors should be represented by UNKNOWN/AMBIGUOUS rather than 
forcing arbitrary distinctions. These normally escalate.

---

## Methodology note
Regex-based keyword bucketing was used only as an EDA proxy to discover 
candidate categories and estimate rough coverage — it is NOT the production 
classification method (see TRD §7.2, which uses an LLM/classifier interface). 
Two rounds of unmatched-sample inspection were performed to surface missed 
categories before freezing this taxonomy.