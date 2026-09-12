# Decision Log — Customer Support AI Agent

## 1. Brand Selection: AmazonHelp
**Decision:** Selected AmazonHelp as the single brand for MVP scope.
**Alternatives considered:** AppleSupport, Uber_Support (top volume candidates).
**Rationale:** Highest volume (169,840 replies) + customer diversity (71,049 
unique) + engagement depth (2.39 replies/customer); domain (orders/delivery/
refunds) matches PRD's own illustrative scenarios.
**Trade-off:** AmazonHelp has significant multilingual content (~25% non-English), 
requiring a language-filter preprocessing step.
**Revisit if:** English-only filtering meaningfully biases golden-set representativeness.

## 2. Language Filtering: English-only via langdetect
**Decision:** Filter to English-language conversations only (25.1% excluded).
**Alternatives considered:** Multilingual support from day one.
**Rationale:** MVP scope; multilingual grounding/evaluation adds complexity 
disproportionate to internship timeline; verified via manual sample inspection 
that exclusions were genuinely non-English, not a langdetect false-positive bug.
**Revisit if:** Future scope expansion to multilingual support (see PRD §33).

## 3. Intent Taxonomy Discovery Method
**Decision:** Regex-based keyword bucketing used as an EDA proxy only, followed 
by 2 rounds of unmatched-sample inspection to surface missed categories, 
resulting in 16 intents + UNKNOWN/AMBIGUOUS.
**Alternatives considered:** Unsupervised clustering (embeddings + k-means).
**Rationale:** Regex is fast, interpretable, and sufficient for discovering 
candidate categories; final taxonomy validated against real message samples, 
not just keyword frequency.
**Trade-off:** Regex proxy only matched final manual label 50.2% of the time — 
confirms manual review was necessary, not just a formality.
**Revisit if:** Production classifier reveals systematic taxonomy overlap/confusion.

## 4. Golden Set Sampling: Stratified, not random
**Decision:** Stratified sample (211 examples) targeting minimum coverage per 
candidate intent bucket, rather than pure random sampling.
**Alternatives considered:** Simple random sample of 200 examples.
**Rationale:** Random sampling would have under-represented rare intents 
(e.g., feature_request at 0.8% raw frequency) to the point of being 
unevaluable; PRD §21 explicitly requires coverage of rare/ambiguous/high-risk cases.
**Trade-off:** Some final categories still ended up thin after manual relabeling 
(prime_membership n=1, packaging_feedback n=2, device_tech_support n=5, 
repair_service_status n=6) — per-intent metrics for these will be statistically 
unreliable and will be reported with this caveat rather than hidden.
**Revisit if:** Additional targeted sampling becomes feasible for thin categories.

## 5. Escalation Labeling Policy
**Decision:** Any explicit financial ask (refund/charge dispute), explicit 
human request, or unresolved-after-multiple-contact-attempts case labeled 
ESCALATE regardless of resolution tone in the conversation.
**Alternatives considered:** Escalate only visibly unresolved/angry conversations.
**Rationale:** PRD §16 requires conservative automation; a calmly-resolved 
financial dispute is still a financial dispute — the *type* of request drives 
escalation, not how smoothly the brand handled it in the historical data.
**Result:** 51.7% escalation rate in the golden set — reflects genuine safety-
first labeling, not an artifact of picking difficult examples.
**Revisit if:** Operating-point tuning on dev data suggests this threshold is 
overly conservative for acceptable automation rate.