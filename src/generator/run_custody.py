
import argparse
import time

from src.database.connection import SessionLocal
from src.database.models import Shipment, CustodyEvent
from src.generator.custody_generator import (
    generate_shipments_and_events_batch,
    bulk_insert_shipments_and_events,
)
from src.services.custody_service import CustodyService


SCALE_CONFIG = {
    "starter": 250,
    "full": 10000,
}


def run(scale="starter", seed=20261022):

    shipment_count = SCALE_CONFIG.get(scale, 250)

    print(
        f"Starting Custody Generation "
        f"[{scale.upper()} MODE: {shipment_count} shipments]"
    )

    start_time = time.time()
    db = SessionLocal()

    try:
        # Check for existing shipment records
        existing_count = db.query(Shipment).count()

        if existing_count > 0:
            print(
                f"Found {existing_count} existing shipments."
            )
            print(
                "Existing records will be preserved. "
                "Please use a fresh database for a full starter run."
            )
            return

        # Generate shipment and custody event records
        print("Generating shipments and custody events...")

        shipments, events = generate_shipments_and_events_batch(
            db,
            shipment_count=shipment_count,
            seed=seed,
        )

        # Insert records
        print(
            f"Inserting {len(shipments)} shipments "
            f"and {len(events)} custody events..."
        )

        bulk_insert_shipments_and_events(
            db,
            shipments,
            events,
        )

        elapsed = time.time() - start_time

        print("Generation completed successfully!")
        print("Shipments inserted:", len(shipments))
        print("Custody events inserted:", len(events))
        print(f"Execution time: {elapsed:.2f} seconds")

        # Verify database counts
        print("\nDATABASE VERIFICATION")

        print(
            "Total shipments:",
            db.query(Shipment).count(),
        )

        print(
            "Total custody events:",
            db.query(CustodyEvent).count(),
        )

        # Reconstruct the location of the first asset
        first_event = (
            db.query(CustodyEvent)
            .order_by(CustodyEvent.event_id)
            .first()
        )

        if first_event:

            print("\nLOCATION RECONSTRUCTION")

            result = CustodyService.get_asset_trajectory(
                db,
                first_event.asset_id,
            )

            print("Asset:", result["asset_code"])
            print(
                "Current location:",
                result["current_location"],
            )
            print(
                "Current custodian:",
                result["current_custodian"],
            )
            print(
                "In transit:",
                result["is_in_transit"],
            )
            print(
                "Total events:",
                result["total_events"],
            )

            print("\nEVENT TIMELINE")

            for event in result["trajectory"]:
                print(
                    event["event_timestamp"],
                    event["event_type"],
                    event["from_location"],
                    "->",
                    event["to_location"],
                )

    except Exception as error:
        db.rollback()
        print("Custody generation failed:", error)
        raise

    finally:
        db.close()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Generate shipments and custody events"
    )

    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="starter",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=20261022,
    )

    args = parser.parse_args()

    run(
        scale=args.scale,
        seed=args.seed,
    )
