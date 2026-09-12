import json
import pickle
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from pathlib import Path

GOLDEN_PATH = "data/schemas/golden_set_final.jsonl"
CLEAN_DATA_PATH = "data/processed/amazon_conversations_clean.jsonl"
INDEX_DIR = Path("data/processed/faiss_index")
INDEX_DIR.mkdir(parents=True, exist_ok=True)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # fast, lightweight, good baseline


def load_golden_conv_ids():
    ids = set()
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        for line in f:
            ex = json.loads(line)
            ids.add(ex["conversation_id"])
    return ids


def load_dev_conversations(golden_ids):
    convs = []
    with open(CLEAN_DATA_PATH, encoding="utf-8") as f:
        for line in f:
            conv = json.loads(line)
            if conv["conversation_id"] not in golden_ids:
                convs.append(conv)
    return convs


def build_evidence_units(conversations):
    """
    Har conversation se ek 'evidence unit' banate hai: customer's issue +
    brand ka resolution, dono combined (TRD §8: 'resolution-aware unit,
    preferably a customer issue plus the corresponding brand response').
    """
    units = []
    for conv in conversations:
        turns = conv["turns"]
        customer_turn = next((t for t in turns if t["role"] == "CUSTOMER"), None)
        brand_turn = next((t for t in turns if t["role"] == "BRAND"), None)

        # Edge case: agar brand ne reply hi nahi kiya, evidence ke liye useless hai
        if not customer_turn or not brand_turn:
            continue

        combined_text = f"Customer issue: {customer_turn['cleaned_text']} Resolution: {brand_turn['cleaned_text']}"
        units.append({
            "conversation_id": conv["conversation_id"],
            "customer_text": customer_turn["cleaned_text"],
            "resolution_text": brand_turn["cleaned_text"],
            "combined_text": combined_text,
        })
    return units


def main():
    print("Loading golden set conversation IDs (to exclude from index)...")
    golden_ids = load_golden_conv_ids()
    print(f"Golden IDs to exclude: {len(golden_ids)}")

    print("Loading dev conversations...")
    dev_convs = load_dev_conversations(golden_ids)
    print(f"Dev conversations available: {len(dev_convs)}")

    print("Building evidence units...")
    units = build_evidence_units(dev_convs)
    print(f"Evidence units (with both customer + brand turn): {len(units)}")

    print(f"Loading embedding model: {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Encoding evidence units (this may take a few minutes)...")
    texts = [u["combined_text"] for u in units]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")

    print("Normalizing embeddings for cosine similarity...")
    faiss.normalize_L2(embeddings)

    print("Building FAISS index...")
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # Inner Product on normalized vectors = cosine similarity
    index.add(embeddings)

    print(f"Saving index ({index.ntotal} vectors)...")
    faiss.write_index(index, str(INDEX_DIR / "amazon_evidence.index"))

    # Metadata alag save karo (FAISS sirf vectors store karta hai, ID/text nahi)
    with open(INDEX_DIR / "evidence_metadata.pkl", "wb") as f:
        pickle.dump(units, f)

    print(f"Saved index and metadata to {INDEX_DIR}")


if __name__ == "__main__":
    main()