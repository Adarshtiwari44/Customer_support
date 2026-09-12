import pickle
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from pathlib import Path

from customer_support.agent.state import AgentState
from customer_support.config.setting import settings

INDEX_DIR = Path("data/processed/faiss_index")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_model = None
_index = None
_metadata = None


def _load_resources():
    """Index/model/metadata ko sirf ek baar load karo (lazy singleton pattern)."""
    global _model, _index, _metadata
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    if _index is None:
        _index = faiss.read_index(str(INDEX_DIR / "amazon_evidence.index"))
    if _metadata is None:
        with open(INDEX_DIR / "evidence_metadata.pkl", "rb") as f:
            _metadata = pickle.load(f)
    return _model, _index, _metadata


def _assess_evidence_quality(scores: list) -> str:
    """
    TRD: 'evidence quality thresholds influence escalation.'
    Simple heuristic abhi: top score aur spread dekh ke quality decide karo.
    """
    if not scores:
        return "NONE"
    top_score = scores[0]
    if top_score < settings.EVIDENCE_THRESHOLD:
        return "WEAK"
    # Agar top scores ka spread bahut zyada hai (contradictory-ish signal),
    # abhi simple rakhte hai - future me actual resolution-text comparison add karenge
    return "STRONG"


def retrieve_evidence(state: AgentState) -> AgentState:
    """
    Current message ke liye relevant historical evidence FAISS se retrieve karta hai.
    Brand-filtering already index-build-time par ho chuka hai (single-brand MVP).
    """
    current_message = state.get("current_message", "")
    errors = list(state.get("errors", []))

    # Edge case: khali message -> evidence retrieve karne ka matlab hi nahi
    if not current_message or not current_message.strip():
        return {
            **state,
            "evidence": [],
            "evidence_quality": "NONE",
            "errors": errors + ["retriever: skipped, empty message"],
        }

    try:
        model, index, metadata = _load_resources()

        # Include conversation context in query for better retrieval
        context_turns = state.get("relevant_context", [])
        query_text = current_message
        if context_turns:
            # Combine last 2 turns with current message for context-aware retrieval
            recent_context = " ".join([t['cleaned_text'] for t in context_turns[-2:]])
            query_text = f"{recent_context} {current_message}"

        query_vec = model.encode([query_text], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(query_vec)

        top_k = settings.RETRIEVAL_TOP_K
        scores, indices = index.search(query_vec, top_k)
        scores = scores[0].tolist()
        indices = indices[0].tolist()

        evidence = []
        seen_resolutions = set()  # near-duplicate evidence hatane ke liye

        for score, idx in zip(scores, indices):
            if idx < 0 or idx >= len(metadata):
                continue  # edge case: FAISS ne invalid index return kiya (kam results available hone par)

            item = metadata[idx]

            # Edge case: duplicate/near-duplicate resolution text skip karo
            dedup_key = item["resolution_text"][:100]
            if dedup_key in seen_resolutions:
                continue
            seen_resolutions.add(dedup_key)

            evidence.append({
                "evidence_id": f"EV-{item['conversation_id']}",
                "conversation_id": item["conversation_id"],
                "relevance_score": round(float(score), 4),
                "resolution_text": item["resolution_text"],
                "source_turns": [
                    {"role": "CUSTOMER", "cleaned_text": item["customer_text"]},
                    {"role": "BRAND", "cleaned_text": item["resolution_text"]},
                ],
            })

        evidence_quality = _assess_evidence_quality([e["relevance_score"] for e in evidence])

        return {
            **state,
            "evidence": evidence,
            "evidence_quality": evidence_quality,
            "errors": errors,
        }

    except FileNotFoundError as e:
        # Index missing -> retrieval unavailable, NEVER claim grounding
        errors.append(f"retriever: index files not found ({e}) -> no evidence")
        return {**state, "evidence": [], "evidence_quality": "NONE", "errors": errors}

    except Exception as e:
        # Koi bhi unexpected failure -> fail safe, evidence khali, kabhi fabricate mat karo
        errors.append(f"retriever: retrieval failed ({type(e).__name__}) -> no evidence")
        return {**state, "evidence": [], "evidence_quality": "NONE", "errors": errors}
    