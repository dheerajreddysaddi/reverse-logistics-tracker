
"""
Stage 7: Evaluation Metrics Engine.

Calculates confusion matrix, accuracy, precision,
recall, specificity and F1 score.
"""

from typing import Dict, Any, List

from sqlalchemy.orm import Session

from src.services.anomaly_detector import AnomalyDetector
from src.services.ground_truth import (
    build_and_save_ground_truth,
    RULE_CODES,
)


def calculate_metrics(tp, fp, fn, tn):
    """Calculate standard binary classification metrics."""

    total = tp + fp + fn + tn

    precision = (
        tp / (tp + fp)
        if (tp + fp) > 0 else 0.0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn) > 0 else 0.0
    )

    specificity = (
        tn / (tn + fp)
        if (tn + fp) > 0 else 0.0
    )

    accuracy = (
        (tp + tn) / total
        if total > 0 else 0.0
    )

    f1_score = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0 else 0.0
    )

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "f1_score": round(f1_score, 4),
    }


class EvaluationEngine:

    @staticmethod
    def evaluate(db: Session) -> Dict[str, Any]:
        """
        Compare detected anomalies with the ground truth.
        """

        # Build the benchmark from Stage 6 markers.
        ground_truth = build_and_save_ground_truth(db)

        # Run all five detection rules.
        detected_anomalies = AnomalyDetector.scan_all(db)

        # Group detected rule codes by asset.
        detected_by_asset: Dict[str, List[str]] = {}

        for detection in detected_anomalies:

            asset_id = str(detection["asset_id"])
            rule_code = detection["rule_code"]

            detected_by_asset.setdefault(
                asset_id, []
            )

            if rule_code not in detected_by_asset[asset_id]:
                detected_by_asset[asset_id].append(rule_code)

        # --------------------------------------------
        # Overall asset-level confusion matrix
        # --------------------------------------------

        tp = 0
        fp = 0
        fn = 0
        tn = 0

        for asset_id, actual in ground_truth.items():

            actual_anomaly = actual["is_anomaly"]
            predicted_anomaly = asset_id in detected_by_asset

            if actual_anomaly and predicted_anomaly:
                tp += 1

            elif not actual_anomaly and predicted_anomaly:
                fp += 1

            elif actual_anomaly and not predicted_anomaly:
                fn += 1

            else:
                tn += 1

        aggregate_metrics = calculate_metrics(
            tp, fp, fn, tn
        )

        # --------------------------------------------
        # Per-rule evaluation
        # --------------------------------------------

        rule_breakdown = {}

        for rule_code in RULE_CODES:

            rule_tp = 0
            rule_fp = 0
            rule_fn = 0
            rule_tn = 0

            for asset_id, actual in ground_truth.items():

                expected = (
                    rule_code in actual["expected_rules"]
                )

                detected = (
                    rule_code in detected_by_asset.get(
                        asset_id, []
                    )
                )

                if expected and detected:
                    rule_tp += 1

                elif not expected and detected:
                    rule_fp += 1

                elif expected and not detected:
                    rule_fn += 1

                else:
                    rule_tn += 1

            rule_metrics = calculate_metrics(
                rule_tp,
                rule_fp,
                rule_fn,
                rule_tn,
            )

            rule_breakdown[rule_code] = {
                "true_positives": rule_tp,
                "false_positives": rule_fp,
                "false_negatives": rule_fn,
                "true_negatives": rule_tn,
                "precision": rule_metrics["precision"],
                "recall": rule_metrics["recall"],
                "specificity": rule_metrics["specificity"],
                "accuracy": rule_metrics["accuracy"],
                "f1_score": rule_metrics["f1_score"],
            }

        total_assets = len(ground_truth)

        return {
            "dataset_summary": {
                "total_evaluated_assets": total_assets,
                "ground_truth_anomalies": tp + fn,
                "ground_truth_clean": tn + fp,
                "total_detected_anomalies": len(
                    detected_by_asset
                ),
                "total_detection_alerts": len(
                    detected_anomalies
                ),
            },

            "confusion_matrix": {
                "true_positives": tp,
                "false_positives": fp,
                "true_negatives": tn,
                "false_negatives": fn,
                "TP": tp,
                "FP": fp,
                "TN": tn,
                "FN": fn,
            },

            "aggregate_metrics": aggregate_metrics,
            "performance": {
                "Accuracy": aggregate_metrics["accuracy"],
                "Precision": aggregate_metrics["precision"],
                "Recall": aggregate_metrics["recall"],
                "Specificity": aggregate_metrics["specificity"],
                "F1-Score": aggregate_metrics["f1_score"],
            },

            "rule_breakdown": rule_breakdown,
        }
