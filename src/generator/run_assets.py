
"""
Command-line runner for reusable asset generation.

Usage:
    python -m src.generator.run_assets --mode starter
    python -m src.generator.run_assets --mode full
"""

import argparse

from src.database.connection import SessionLocal
from src.database.models import ReusableAsset
from src.generator.asset_generator import (
    PROJECT_SEED,
    bulk_insert_assets,
    generate_assets_batch,
)


ASSET_COUNTS = {
    "starter": 500,
    "full": 20000,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate reusable logistics assets."
    )

    parser.add_argument(
        "--mode",
        choices=["starter", "full"],
        default="starter",
        help="Dataset size: starter (500) or full (20000).",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=PROJECT_SEED,
        help="Random seed for reproducible generation.",
    )

    args = parser.parse_args()

    asset_count = ASSET_COUNTS[args.mode]

    db = SessionLocal()

    try:
        existing_count = db.query(ReusableAsset).count()

        if existing_count > 0:
            raise SystemExit(
                f"Database already contains {existing_count} assets. "
                "Insertion cancelled to prevent duplicates."
            )

        print(f"Generation mode: {args.mode}")
        print(f"Assets to generate: {asset_count}")
        print(f"Random seed: {args.seed}")

        records = generate_assets_batch(
            db=db,
            count=asset_count,
            seed=args.seed,
        )

        print("Asset records generated successfully.")
        print("Inserting records into database...")

        bulk_insert_assets(
            db=db,
            asset_records=records,
        )

        final_count = db.query(ReusableAsset).count()

        print("\nAsset generation completed successfully!")
        print(f"Total assets in database: {final_count}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
