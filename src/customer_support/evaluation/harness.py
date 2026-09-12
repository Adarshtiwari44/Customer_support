import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from sklearn.metrics import classification_report, accuracy_score, precision_recall_fscore_support

from customer_support.agent.graph import app as agent_app
from customer_support.config.setting import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_GOLDEN_SET_PATH = BASE_DIR / "data" / "schemas" / "golden_set_final.jsonl"
DEFAULT_REPORTS_DIR = BASE_DIR / "evaluation" / "reports"


def load_golden_set(filepath: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Golden set JSONL file load karta hai."""
    path = filepath or DEFAULT_GOLDEN_SET_PATH
    if not path.exists():
        raise FileNotFoundError(f"Golden set not found at: {path}")

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def evaluate_example(example: Dict[str, Any]) -> Dict[str, Any]:
    """Ek single golden set example ko pipeline se run karta hai aur prediction record karta hai."""
    current_message = example.get("current_message", "")
    context = example.get("context", [])

    # ConversationTurn format me format karo
    context_turns = [
        {
            "tweet_id": turn.get("tweet_id", ""),
            "author_id": turn.get("author_id", ""),
            "role": turn.get("role", "CUSTOMER"),
            "text": turn.get("text", ""),
            "cleaned_text": turn.get("cleaned_text", turn.get("text", "")),
        }
        for turn in context
    ]

    initial_state = {
        "brand_id": example.get("brand_id", settings.BRAND_ID),
        "conversation_id": example.get("conversation_id"),
        "current_message": current_message,
        "context_turns": context_turns,
        "prediction_id": f"eval-{example.get('example_id', 'unknown')}",
        "errors": [],
    }

    start_time = time.perf_counter()
    try:
        result = agent_app.invoke(initial_state)
        latency_ms = (time.perf_counter() - start_time) * 1000
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Error evaluating {example.get('example_id')}: {e}")
        return {
            "example_id": example.get("example_id"),
            "gold_intent": example.get("gold_intent"),
            "pred_intent": "UNKNOWN",
            "gold_escalation": example.get("gold_escalation"),
            "pred_escalation": "ESCALATE",
            "confidence": 0.0,
            "confidence_tier": "LOW",
            "evidence_quality": "NONE",
            "response_valid": False,
            "high_risk": True,
            "draft_response": None,
            "latency_ms": latency_ms,
            "errors": [f"pipeline execution failed: {type(e).__name__} ({str(e)})"],
            "escalation_reason": "pipeline error",
        }

    return {
        "example_id": example.get("example_id"),
        "gold_intent": example.get("gold_intent"),
        "pred_intent": result.get("intent", "UNKNOWN"),
        "gold_escalation": example.get("gold_escalation"),
        "pred_escalation": result.get("decision", "ESCALATE"),
        "confidence": result.get("confidence", 0.0),
        "confidence_tier": result.get("confidence_tier", "LOW"),
        "evidence_quality": result.get("evidence_quality", "NONE"),
        "response_valid": result.get("response_valid"),
        "high_risk": result.get("high_risk", False),
        "draft_response": result.get("draft_response"),
        "latency_ms": latency_ms,
        "errors": result.get("errors", []),
        "escalation_reason": result.get("escalation_reason"),
    }


def compute_metrics(eval_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Predictions aur Ground Truth se accuracy, precision, recall, F1, aur safety metrics calculate karta hai."""
    gold_intents = [r["gold_intent"] for r in eval_records]
    pred_intents = [r["pred_intent"] for r in eval_records]

    gold_escalations = [r["gold_escalation"] for r in eval_records]
    pred_escalations = [r["pred_escalation"] for r in eval_records]

    # ---- Intent Metrics ----
    intent_acc = accuracy_score(gold_intents, pred_intents)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        gold_intents, pred_intents, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        gold_intents, pred_intents, average="weighted", zero_division=0
    )
    per_class_report = classification_report(
        gold_intents, pred_intents, output_dict=True, zero_division=0
    )

    # ---- Escalation / Routing Metrics ----
    escalation_acc = accuracy_score(gold_escalations, pred_escalations)

    # Confusion matrix for escalation (Positive = ESCALATE, Negative = AUTO_HANDLE)
    tp = sum(1 for g, p in zip(gold_escalations, pred_escalations) if g == "ESCALATE" and p == "ESCALATE")
    fp = sum(1 for g, p in zip(gold_escalations, pred_escalations) if g == "AUTO_HANDLE" and p == "ESCALATE")
    tn = sum(1 for g, p in zip(gold_escalations, pred_escalations) if g == "AUTO_HANDLE" and p == "AUTO_HANDLE")
    fn = sum(1 for g, p in zip(gold_escalations, pred_escalations) if g == "ESCALATE" and p == "AUTO_HANDLE")

    # Metrics
    escalate_precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    escalate_recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    escalate_f1 = (
        2 * (escalate_precision * escalate_recall) / (escalate_precision + escalate_recall)
        if (escalate_precision + escalate_recall) > 0 else 0.0
    )

    # Safety-critical metric: When AI says AUTO_HANDLE, was it actually safe?
    # False Negative (FN) is dangerous: AI auto-handled something that should have escalated.
    auto_handle_precision = tn / (tn + fn) if (tn + fn) > 0 else 0.0

    # System-level metrics
    latencies = [r["latency_ms"] for r in eval_records]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    errors_count = sum(1 for r in eval_records if r["errors"])

    return {
        "sample_size": len(eval_records),
        "intent_classification": {
            "accuracy": float(intent_acc),
            "macro_precision": float(macro_p),
            "macro_recall": float(macro_r),
            "macro_f1": float(macro_f1),
            "weighted_f1": float(weighted_f1),
            "per_class": per_class_report,
        },
        "escalation_routing": {
            "accuracy": float(escalation_acc),
            "escalation_precision": float(escalate_precision),
            "escalation_recall": float(escalate_recall),
            "escalation_f1": float(escalate_f1),
            "auto_handle_safety_precision": float(auto_handle_precision),
            "confusion_matrix": {
                "true_escalate (TP)": tp,
                "false_escalate_overcautious (FP)": fp,
                "true_autohandle (TN)": tn,
                "unsafe_autohandle_dangerous (FN)": fn,
            },
            "system_escalation_rate": float(sum(1 for p in pred_escalations if p == "ESCALATE") / len(pred_escalations)),
            "gold_escalation_rate": float(sum(1 for g in gold_escalations if g == "ESCALATE") / len(gold_escalations)),
        },
        "system_performance": {
            "avg_latency_ms": round(avg_latency, 2),
            "error_rate": float(errors_count / len(eval_records)) if eval_records else 0.0,
            "total_with_errors": errors_count,
        },
    }


def run_evaluation(
    golden_set_path: Optional[Path] = None,
    limit: Optional[int] = None,
    rate_limit_delay_sec: float = 0.5,
    save_report: bool = True,
    output_filename: str = "pipeline_evaluation_results.json",
) -> Dict[str, Any]:
    """
    Main entrypoint:
    1. Golden set load karta hai
    2. Har sample ko pipeline se pass karta hai
    3. Metrics calculate karta hai
    4. Report save karta hai
    """
    golden_set = load_golden_set(golden_set_path)
    if limit:
        golden_set = golden_set[:limit]

    logger.info(f"Running evaluation on {len(golden_set)} samples...")
    eval_records = []

    for i, example in enumerate(golden_set, 1):
        ex_id = example.get("example_id", f"sample-{i}")
        logger.info(f"[{i}/{len(golden_set)}] Evaluating {ex_id}...")

        record = evaluate_example(example)
        eval_records.append(record)

        if rate_limit_delay_sec > 0 and i < len(golden_set):
            time.sleep(rate_limit_delay_sec)

    metrics = compute_metrics(eval_records)

    if save_report:
        DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = DEFAULT_REPORTS_DIR / output_filename
        detail_path = DEFAULT_REPORTS_DIR / output_filename.replace(".json", "_details.json")

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(eval_records, f, indent=2)

        logger.info(f"Evaluation report saved to: {report_path}")
        logger.info(f"Detailed predictions saved to: {detail_path}")

    return metrics
