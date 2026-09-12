import pandas as pd
import json
from pathlib import Path

RAW_PATH = "data/raw/twcs.csv"
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)
BRAND_ID = "AmazonHelp"


def load_and_normalize_ids(path):
    df = pd.read_csv(path)
    df["tweet_id"] = df["tweet_id"].astype(str)
    df["in_response_to_tweet_id"] = df["in_response_to_tweet_id"].apply(
        lambda x: str(int(x)) if pd.notna(x) else None
    )
    return df


def find_root(tweet_id, lookup, max_hops=30):
    current = tweet_id
    hops = 0
    while hops < max_hops:
        if current not in lookup.index:
            return current
        parent = lookup.loc[current, "in_response_to_tweet_id"]
        if parent is None:
            return current
        current = parent
        hops += 1
    return current


def build_children_map(df):
    """Har tweet ke 'reply' children kaun kaun hai, uska reverse map banao."""
    children = {}
    for tid, parent in zip(df["tweet_id"], df["in_response_to_tweet_id"]):
        if parent is not None:
            children.setdefault(parent, []).append(tid)
    return children


def reconstruct_thread(root_id, lookup, children_map, max_turns=20):
    """Root se aage chalte hue ek linear thread banao (single-path, sabse lamba/first child follow karo)."""
    thread = []
    current = root_id
    turns = 0
    while current is not None and turns < max_turns:
        if current not in lookup.index:
            break
        row = lookup.loc[current]
        thread.append({
            "tweet_id": current,
            "author_id": row["author_id"],
            "role": "CUSTOMER" if row["inbound"] else "BRAND",
            "text": row["text"],
            "created_at": row["created_at"],
        })
        kids = children_map.get(current)
        if not kids:
            break
        current = kids[0]  # simple strategy: pehla child follow karo
        turns += 1
    return thread


def main():
    print("Loading dataset...")
    df = load_and_normalize_ids(RAW_PATH)
    lookup = df.set_index("tweet_id")

    print("Finding Amazon-related customer messages...")
    amazon_replies = df[df["author_id"] == BRAND_ID]
    customer_msg_ids = amazon_replies["in_response_to_tweet_id"].dropna().unique()

    print("Finding conversation roots...")
    roots = {tid: find_root(tid, lookup) for tid in customer_msg_ids}
    unique_roots = sorted(set(roots.values()))
    print(f"Unique conversation roots: {len(unique_roots)}")

    print("Building children map (for forward traversal)...")
    children_map = build_children_map(df)

    print("Reconstructing threads...")
    conversations = []
    for i, root_id in enumerate(unique_roots):
        thread = reconstruct_thread(root_id, lookup, children_map)
        # Sirf wahi threads rakho jisme Amazon ka kam se kam 1 reply ho
        if any(t["author_id"] == BRAND_ID for t in thread):
            conversations.append({
                "conversation_id": root_id,
                "turns": thread,
            })
        if i % 10000 == 0:
            print(f"  processed {i}/{len(unique_roots)}")

    print(f"Total reconstructed conversations: {len(conversations)}")

    out_path = OUT_DIR / "amazon_conversations_raw.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for conv in conversations:
            f.write(json.dumps(conv, ensure_ascii=False) + "\n")

    print(f"Saved to {out_path}")

    # Quick sanity check: pehle 2 conversations print karo
    print("\n--- Sample conversation ---")
    print(json.dumps(conversations[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()