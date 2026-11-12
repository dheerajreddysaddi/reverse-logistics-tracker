
"""
Stage 5: Reverse Logistics Execution Runner.

Creates missing RMAs, inspections, repairs and deposit settlements.
Preserves all existing database records.
"""

import argparse
import time

from sqlalchemy import func

from src.database.connection import SessionLocal
from src.database.models import (
    ReturnAuthorization,
    Inspection,
    Repair,
    DepositLedger,
)

from src.generator.rma_generator import (
    generate_reverse_logistics_batch,
    bulk_insert_reverse_logistics,
)


SCALE_CONFIG = {
    "starter": 100,
    "full": 5000,
}


def run(scale="starter", seed=42):

    target_count = SCALE_CONFIG[scale]
    start_time = time.time()

    db = SessionLocal()

    try:
        print(
            f"\n--- Reverse Logistics Engine: "
            f"{scale.upper()} MODE ---"
        )

        existing_count = db.query(ReturnAuthorization).count()

        remaining = max(0, target_count - existing_count)

        print(f"Existing RMAs: {existing_count}")
        print(f"Target RMAs: {target_count}")
        print(f"New RMAs required: {remaining}")

        if remaining > 0:

            print("\nGenerating reverse logistics records...")

            rmas, inspections, repairs, ledgers = (
                generate_reverse_logistics_batch(
                    db,
                    return_count=remaining,
                    seed=seed,
                )
            )

            print(f"Generated RMAs: {len(rmas)}")
            print(f"Generated inspections: {len(inspections)}")
            print(f"Generated repairs: {len(repairs)}")
            print(f"Generated ledger entries: {len(ledgers)}")

            bulk_insert_reverse_logistics(
                db,
                rmas,
                inspections,
                repairs,
                ledgers,
            )

        else:
            print("\nTarget already reached. No new records generated.")

        # Final database counts.
        print("\n--- FINAL DATABASE COUNTS ---")

        total_rmas = db.query(ReturnAuthorization).count()
        total_inspections = db.query(Inspection).count()
        total_repairs = db.query(Repair).count()
        total_ledgers = db.query(DepositLedger).count()

        print(f"Total RMAs: {total_rmas}")
        print(f"Total inspections: {total_inspections}")
        print(f"Total repairs: {total_repairs}")
        print(f"Total ledger entries: {total_ledgers}")

        # Inspection grade breakdown using remarks.
        print("\n--- INSPECTION GRADING ---")

        for grade in ["A", "B", "C", "F"]:

            count = (
                db.query(Inspection)
                .filter(
                    Inspection.remarks.like(f"Grade {grade};%")
                )
                .count()
            )

            print(f"Grade {grade}: {count}")

        # Repair summary.
        print("\n--- REPAIR SUMMARY ---")

        repair_count = db.query(Repair).count()

        repair_cost = (
            db.query(
                func.sum(Repair.repair_cost)
            ).scalar() or 0
        )

        print(f"Total repairs: {repair_count}")
        print(f"Total repair cost: {repair_cost}")

        # Deposit ledger summary.
        print("\n--- DEPOSIT LEDGER SUMMARY ---")

        ledger_summary = (
            db.query(
                DepositLedger.transaction_type,
                func.count(DepositLedger.ledger_id),
                func.sum(DepositLedger.amount),
            )
            .group_by(DepositLedger.transaction_type)
            .all()
        )

        for transaction_type, count, amount in ledger_summary:

            print(
                f"{transaction_type}: "
                f"{count} transactions | Amount: {amount or 0}"
            )

        elapsed = time.time() - start_time

        print(f"\nExecution completed in {elapsed:.2f} seconds.")

    except Exception as error:

        db.rollback()

        print(f"\nReverse logistics failed: {error}")

        raise

    finally:
        db.close()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="starter",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    args = parser.parse_args()

    run(
        scale=args.scale,
        seed=args.seed,
    )

