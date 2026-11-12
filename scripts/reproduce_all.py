"""
Master reproduction pipeline for the Reverse Logistics Tracker.

Runs master-data seeding, asset generation, custody generation,
reverse logistics, anomaly detection, and evaluation.

Existing database records are preserved. This script never resets
or deletes the database.
"""

import argparse

from src.database.connection import SessionLocal
from src.database.models import (
    ReusableAsset,
    Shipment,
    CustodyEvent,
    ReturnAuthorization,
)
from src.database.seed_master import seed_master_data

from src.generator.asset_generator import (
    generate_assets_batch,
    bulk_insert_assets,
)
from src.generator import run_custody
from src.generator import run_reverse_logistics
from src.generator import run_anomalies
from src.services import run_evaluation


ASSET_TARGETS = {
    "starter": 500,
    "full": 20000,
}


def generate_assets_if_needed(scale: str, seed: int) -> None:
    """Generate assets only when the database has no assets."""

    target = ASSET_TARGETS[scale]
    db = SessionLocal()

    try:
        existing = db.query(ReusableAsset).count()

        if existing > 0:
            print(
                f"[ASSETS] Preserving {existing} existing assets. "
                f"Target for {scale}: {target}."
            )

            if existing < target:
                print(
                    "[ASSETS] Existing dataset is smaller than the "
                    "requested target. No additional assets were "
                    "inserted to avoid duplicate deterministic IDs."
                )
            return

        print(f"[ASSETS] Generating {target} assets...")

        records = generate_assets_batch(
            db,
            count=target,
            seed=seed,
        )

        inserted = bulk_insert_assets(db, records)

        print(f"[ASSETS] Inserted {inserted} assets.")

    finally:
        db.close()


def print_database_summary() -> None:
    """Print final operational record counts."""

    db = SessionLocal()

    try:
        print("\n========== DATABASE SUMMARY ==========")
        print(f"Assets:       {db.query(ReusableAsset).count()}")
        print(f"Shipments:    {db.query(Shipment).count()}")
        print(f"Custody:      {db.query(CustodyEvent).count()}")
        print(f"Return RMAs:  {db.query(ReturnAuthorization).count()}")
        print("======================================\n")

    finally:
        db.close()


def reproduce_all(scale: str, seed: int) -> None:
    """Execute the complete data reproduction pipeline."""

    print("\n========================================")
    print(" REVERSE LOGISTICS REPRODUCTION PIPELINE")
    print("========================================")
    print(f"Scale: {scale}")
    print(f"Seed:  {seed}\n")

    print("[1/6] Initializing database and master data...")
    seed_master_data()
    print("[MASTER DATA] Ready.")

    print("\n[2/6] Generating reusable assets...")
    generate_assets_if_needed(scale, seed)

    print("\n[3/6] Generating shipment and custody data...")
    run_custody.run(scale=scale, seed=seed)

    print("\n[4/6] Generating reverse logistics data...")
    run_reverse_logistics.run(scale=scale, seed=seed)

    print("\n[5/6] Injecting and detecting anomalies...")
    run_anomalies.run()

    print("\n[6/6] Evaluating anomaly detection...")
    run_evaluation.run()

    print_database_summary()

    print("REPRODUCTION PIPELINE COMPLETED SUCCESSFULLY.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce the complete reverse logistics dataset."
    )

    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="starter",
        help="Dataset scale: starter or full (default: starter).",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=20261022,
        help="Random seed for reproducible generation.",
    )

    args = parser.parse_args()

    reproduce_all(
        scale=args.scale,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
