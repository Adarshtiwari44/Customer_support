import json
import re
from pathlib import Path
from langdetect import detect, LangDetectException

IN_PATH = Path("data/processed/amazon_conversations_raw.jsonl")
OUT_PATH = Path("data/processed/amazon_conversations_clean.jsonl")
FLAGGED_PATH = Path("data/processed/amazon_conversations_flagged.jsonl")


def clean_text(text: str) -> str:
    """Normalized version banata hai — classification/embedding ke liye"""
    cleaned = text
    cleaned = re.sub(r"https?://\S+", "", cleaned)          # URLs hatao
    cleaned = re.sub(r"@\w+", "", cleaned)                   # @mentions hatao
    cleaned = re.sub(r"\^[A-Z]{1,3}\b", "", cleaned)          # agent signature jaise ^WT hatao
    cleaned = cleaned.replace("&amp;", "and")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()            # extra spaces
    return cleaned


def is_english(text: str) -> bool:
    if not text or len(text.strip()) < 3:
        return False
    try:
        return detect(text) == "en"
    except LangDetectException:
        return False


def main():
    clean_conversations = []
    flagged_conversations = []

    with open(IN_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    print(f"Total conversations to process: {len(lines)}")

    for i, line in enumerate(lines):
        conv = json.loads(line)
        turns = conv["turns"]

        # Har turn me cleaned_text add karo
        for t in turns:
            t["cleaned_text"] = clean_text(t["text"])

        # Conversation-level language check: customer ke pehle turn se judge karo
        first_customer_turn = next((t for t in turns if t["role"] == "CUSTOMER"), None)
        lang_ok = first_customer_turn and is_english(first_customer_turn["cleaned_text"])

        # Malformed check: koi turn khali cleaned_text wala toh nahi
        has_empty_turns = any(len(t["cleaned_text"].strip()) == 0 for t in turns)

        if lang_ok and not has_empty_turns and len(turns) >= 2:
            clean_conversations.append(conv)
        else:
            conv["flag_reason"] = (
                "non_english" if not lang_ok else
                "empty_turn" if has_empty_turns else
                "too_short"
            )
            flagged_conversations.append(conv)

        if i % 10000 == 0:
            print(f"  processed {i}/{len(lines)}")

    print(f"\nClean conversations: {len(clean_conversations)}")
    print(f"Flagged (excluded) conversations: {len(flagged_conversations)}")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for c in clean_conversations:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    with open(FLAGGED_PATH, "w", encoding="utf-8") as f:
        for c in flagged_conversations:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"Saved clean -> {OUT_PATH}")
    print(f"Saved flagged -> {FLAGGED_PATH}")


if __name__ == "__main__":
    main()