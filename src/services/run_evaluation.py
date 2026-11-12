
"""
Stage 7: Evaluation Runner.

Runs the evaluation engine, prints the scorecard,
and saves evaluation_report.json.
"""

import json
import os

from src.database.connection import SessionLocal

from src.services.evaluation_metrics import EvaluationEngine


def run():

    print(
        "\n--- Stage 7: Anomaly Detection Evaluation ---"
    )

    db = SessionLocal()

    try:

        report = EvaluationEngine.evaluate(db)

        base_dir = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )

        output_dir = os.path.join(
            base_dir,
            "data",
            "processed",
        )

        os.makedirs(output_dir, exist_ok=True)

        report_path = os.path.join(
            output_dir,
            "evaluation_report.json",
        )

        with open(
            report_path,
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(report, file, indent=2)

        summary = report["dataset_summary"]
        cm = report["confusion_matrix"]
        metrics = report["aggregate_metrics"]

        print("\n=== DATASET SUMMARY ===")

        print(
            f"Total Assets Evaluated : "
            f"{summary['total_evaluated_assets']}"
        )

        print(
            f"Ground Truth Anomalies : "
            f"{summary['ground_truth_anomalies']}"
        )

        print(
            f"Ground Truth Clean     : "
            f"{summary['ground_truth_clean']}"
        )

        print("\n=== CONFUSION MATRIX ===")

        print(
            f"True Positives (TP)  : {cm['true_positives']}"
        )

        print(
            f"False Positives (FP) : {cm['false_positives']}"
        )

        print(
            f"False Negatives (FN) : {cm['false_negatives']}"
        )

        print(
            f"True Negatives (TN)  : {cm['true_negatives']}"
        )

        print("\n=== SYSTEM PERFORMANCE METRICS ===")

        print(
            f"Accuracy    : {metrics['accuracy'] * 100:.2f}%"
        )

        print(
            f"Precision   : {metrics['precision'] * 100:.2f}%"
        )

        print(
            f"Recall      : {metrics['recall'] * 100:.2f}%"
        )

        print(
            f"Specificity : {metrics['specificity'] * 100:.2f}%"
        )

        print(
            f"F1-Score    : {metrics['f1_score'] * 100:.2f}%"
        )

        print("\n=== PER-RULE EVALUATION ===")

        print(
            f"{'Rule':<10} | {'TP':<4} | {'FP':<4} | "
            f"{'FN':<4} | {'Precision':<10} | "
            f"{'Recall':<10} | {'F1-Score':<10}"
        )

        print("-" * 75)

        for rule, data in report["rule_breakdown"].items():

            print(
                f"{rule:<10} | "
                f"{data['true_positives']:<4} | "
                f"{data['false_positives']:<4} | "
                f"{data['false_negatives']:<4} | "
                f"{data['precision'] * 100:>8.1f}% | "
                f"{data['recall'] * 100:>8.1f}% | "
                f"{data['f1_score'] * 100:>8.1f}%"
            )

        print("\nEvaluation report saved to:")
        print("data/processed/evaluation_report.json")

        print("\nStage 7 evaluation completed.")

    except Exception as error:

        print(f"\nEvaluation failed: {error}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    run()
