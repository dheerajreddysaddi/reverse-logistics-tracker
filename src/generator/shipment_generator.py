
"""
Synthetic shipment generation engine.

Generates deterministic shipment records using
the existing SQLAlchemy database models.
"""

import random

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from src.database.models import Location, Shipment
from src.generator.id_generator import generate_shipment_id


PROJECT_SEED = 20261022

SIMULATION_DATE = datetime(2026, 10, 22, 23, 59, 59)

CARRIERS = [
    "DHL",
    "FedEx",
    "Blue Dart",
    "Delhivery",
    "DTDC",
]

STATUS_OPTIONS = [
    "planned",
    "dispatched",
    "delivered",
    "cancelled",
]

STATUS_WEIGHTS = [10, 15, 65, 10]


def generate_shipments_batch(
    db: Session,
    count: int = 250,
    seed: int = PROJECT_SEED,
) -> list[dict[str, Any]]:
    """
    Generate deterministic shipment records.

    The returned records are ready for database insertion.
    """

    if count <= 0:
        raise ValueError("Shipment count must be greater than zero.")

    rng = random.Random(seed)

    locations = (
        db.query(Location)
        .filter(Location.is_active.is_(True))
        .order_by(Location.location_id)
        .all()
    )

    if len(locations) < 2:
        raise ValueError(
            "At least two active locations are required."
        )

    shipment_records = []

    start_date = datetime(2024, 1, 1)

    available_days = (
        SIMULATION_DATE.date() - start_date.date()
    ).days

    for index in range(1, count + 1):

        origin, destination = rng.sample(locations, 2)

        dispatch_date = start_date + timedelta(
            days=rng.randint(0, available_days),
            hours=rng.randint(6, 18),
        )

        expected_delivery_date = dispatch_date + timedelta(
            days=rng.randint(2, 7)
        )

        shipment_status = rng.choices(
            STATUS_OPTIONS,
            weights=STATUS_WEIGHTS,
            k=1,
        )[0]

        actual_delivery_date = None

        if shipment_status == "delivered":
            actual_delivery_date = dispatch_date + timedelta(
                days=rng.randint(1, 9)
            )

        shipment_records.append(
            {
                "shipment_code": generate_shipment_id(index),
                "origin_location_id": origin.location_id,
                "destination_location_id": destination.location_id,
                "carrier_name": rng.choice(CARRIERS),
                "dispatch_date": dispatch_date,
                "expected_delivery_date": expected_delivery_date,
                "actual_delivery_date": actual_delivery_date,
                "shipment_status": shipment_status,
            }
        )

    return shipment_records


def bulk_insert_shipments(
    db: Session,
    shipment_records: list[dict[str, Any]],
    batch_size: int = 2000,
) -> None:
    """
    Insert shipment records in batches.

    All batches are committed together.
    """

    if batch_size <= 0:
        raise ValueError("Batch size must be greater than zero.")

    try:
        for start in range(0, len(shipment_records), batch_size):
            chunk = shipment_records[start:start + batch_size]

            db.bulk_insert_mappings(
                Shipment,
                chunk,
            )

        db.commit()

    except Exception:
        db.rollback()
        raise
