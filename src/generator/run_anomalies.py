
"""
Stage 6: Anomaly Injection and Detection Runner.
"""

from src.database.connection import SessionLocal

from src.generator.anomaly_injector import (
    inject_mandatory_edge_cases,
)

from src.services.anomaly_detector import AnomalyDetector


def run():

    print("\n--- Stage 6: Anomaly Detection Engine ---")

    db = SessionLocal()

    try:

        print("\nInjecting controlled test anomalies...")

        ground_truth = inject_mandatory_edge_cases(db)

        if ground_truth:
            print(
                f"Injected {len(ground_truth)} test anomalies."
            )
        else:
            print("Existing Stage 6 test data will be reused.")

        print("\nRunning all five business rules...")

        detected = AnomalyDetector.scan_all(db)

        print(f"\nDetected violations: {len(detected)}")

        print("\n" + "-" * 105)

        print(
            f"{'RULE':<12} | "
            f"{'SEVERITY':<10} | "
            f"{'ASSET ID':<12} | "
            f"DETAILS"
        )

        print("-" * 105)

        for anomaly in detected:

            print(
                f"{anomaly['rule_code']:<12} | "
                f"{anomaly['severity']:<10} | "
                f"{str(anomaly['asset_id']):<12} | "
                f"{anomaly['details']}"
            )

        print("-" * 105)

        print("\n--- RULE SUMMARY ---")

        expected_rules = [
            "ANOM-01",
            "ANOM-02",
            "ANOM-03",
            "ANOM-04",
            "ANOM-05",
        ]

        for rule in expected_rules:

            count = sum(
                1
                for item in detected
                if item["rule_code"] == rule
            )

            print(f"{rule}: {count} detected")

        print("\nStage 6 detection run completed.")

    except Exception as error:

        db.rollback()

        print(f"\nStage 6 failed: {error}")

        raise

    finally:
        db.close()


if __name__ == "__main__":
    run()
