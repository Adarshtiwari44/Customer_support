import argparse
import json
from pathlib import Path
from customer_support.evaluation.harness import run_evaluation


def main():
    parser = argparse.ArgumentParser(description="Run Evaluation Harness on Golden Set")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of examples to evaluate (e.g. 5, 10, 20 for quick testing)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between LLM calls to avoid Groq rate limits (default: 1.0s)",
    )
    parser.add_argument(
        "--golden-set",
        type=str,
        default=None,
        help="Path to custom golden set JSONL file (optional)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="pipeline_evaluation_results.json",
        help="Output filename for evaluation report (saved in evaluation/reports/)",
    )

    args = parser.parse_args()

    golden_path = Path(args.golden_set) if args.golden_set else None

    print("\n" + "=" * 60)
    print("STARTING PIPELINE EVALUATION HARNESS")
    print(f"   Limit:     {args.limit if args.limit else 'All 211 samples'}")
    print(f"   Delay:     {args.delay}s per sample")
    print(f"   Output:    evaluation/reports/{args.output}")
    print("=" * 60 + "\n")

    metrics = run_evaluation(
        golden_set_path=golden_path,
        limit=args.limit,
        rate_limit_delay_sec=args.delay,
        save_report=True,
        output_filename=args.output,
    )

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS SUMMARY")
    print("=" * 60)

    print(f"\n[Intent Classification]")
    print(f"  - Overall Accuracy:    {metrics['intent_classification']['accuracy'] * 100:.2f}%")
    print(f"  - Macro F1:            {metrics['intent_classification']['macro_f1'] * 100:.2f}%")
    print(f"  - Weighted F1:         {metrics['intent_classification']['weighted_f1'] * 100:.2f}%")

    print(f"\n[Escalation / Routing Safety]")
    print(f"  - Routing Accuracy:    {metrics['escalation_routing']['accuracy'] * 100:.2f}%")
    print(f"  - Escalation Recall:   {metrics['escalation_routing']['escalation_recall'] * 100:.2f}%")
    print(f"  - Auto-Handle Safety:  {metrics['escalation_routing']['auto_handle_safety_precision'] * 100:.2f}%")
    print(f"  - System Esc. Rate:    {metrics['escalation_routing']['system_escalation_rate'] * 100:.2f}%")
    print(f"  - Gold Esc. Rate:      {metrics['escalation_routing']['gold_escalation_rate'] * 100:.2f}%")

    cm = metrics['escalation_routing']['confusion_matrix']
    print(f"\n[Escalation Confusion Matrix]")
    print(f"  - True Escalations (TP):               {cm['true_escalate (TP)']}")
    print(f"  - Overcautious Escalations (FP):       {cm['false_escalate_overcautious (FP)']}")
    print(f"  - True Auto-Handles (TN):              {cm['true_autohandle (TN)']}")
    print(f"  - Unsafe Auto-Handles (FN - Risk!):    {cm['unsafe_autohandle_dangerous (FN)']}")

    print(f"\n[System Performance]")
    print(f"  - Avg Latency:         {metrics['system_performance']['avg_latency_ms']} ms")
    print(f"  - Error Rate:          {metrics['system_performance']['error_rate'] * 100:.1f}%")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
