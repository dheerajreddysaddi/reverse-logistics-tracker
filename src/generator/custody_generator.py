
import random
import re

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from src.database.models import (
    Location,
    ReusableAsset,
    Shipment,
    CustodyEvent,
)

from src.generator.id_generator import generate_shipment_id


PROJECT_SEED = 20261022

CARRIERS = [
    "DHL Supply Chain",
    "FedEx Freight",
    "Blue Dart",
    "Delhivery",
    "DTDC",
]

ACTORS = {
    "dispatch": "Dispatch Clerk T. Jenkins",
    "transfer": "Carrier Hub Operator A. Davis",
    "receipt": "Warehouse Receiving Agent R. Vance",
}


def generate_shipments_and_events_batch(
    db: Session,
    shipment_count: int = 250,
    seed: int = PROJECT_SEED,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:

    if shipment_count <= 0:
        raise ValueError("Shipment count must be greater than zero.")

    rng = random.Random(seed)

    locations = (
        db.query(Location)
        .filter(Location.is_active.is_(True))
        .order_by(Location.location_id)
        .all()
    )

    if len(locations) < 3:
        raise ValueError("At least three active locations are required.")

    # Exclude assets that already have custody events.
    used_asset_ids = db.query(CustodyEvent.asset_id).distinct()

    assets = (
        db.query(ReusableAsset)
        .filter(~ReusableAsset.asset_id.in_(used_asset_ids))
        .order_by(ReusableAsset.asset_id)
        .limit(shipment_count)
        .all()
    )

    if len(assets) < shipment_count:
        raise ValueError(
            f"Requested {shipment_count} shipments, "
            f"but only {len(assets)} unused assets are available."
        )

    # Find the highest existing shipment number.
    existing_codes = [
        code for (code,) in db.query(Shipment.shipment_code).all()
    ]

    numbers = []

    for code in existing_codes:
        match = re.search(r"(\d+)$", code)
        if match:
            numbers.append(int(match.group(1)))

    next_number = max(numbers, default=0) + 1

    shipment_records = []
    custody_event_records = []

    for offset, asset in enumerate(assets):

        origin, transit_hub, destination = rng.sample(locations, 3)

        carrier = rng.choice(CARRIERS)

        shipment_code = generate_shipment_id(
            next_number + offset
        )

        dispatch_date = asset.created_at + timedelta(
            days=rng.randint(1, 15),
            hours=rng.randint(1, 8),
        )

        transit_date = dispatch_date + timedelta(
            hours=rng.randint(8, 18)
        )

        transfer_date = transit_date + timedelta(
            hours=rng.randint(4, 12)
        )

        receipt_date = transfer_date + timedelta(
            hours=rng.randint(2, 8)
        )

        is_delivered = rng.random() < 0.80

        expected_delivery_date = dispatch_date + timedelta(days=3)

        shipment_records.append({
            "shipment_code": shipment_code,
            "origin_location_id": origin.location_id,
            "destination_location_id": destination.location_id,
            "carrier_name": carrier,
            "dispatch_date": dispatch_date,
            "expected_delivery_date": expected_delivery_date,
            "actual_delivery_date": receipt_date if is_delivered else None,
            "shipment_status": "delivered" if is_delivered else "dispatched",
        })

        custody_event_records.append({
            "asset_id": asset.asset_id,
            "shipment_code": shipment_code,
            "from_location_id": origin.location_id,
            "to_location_id": transit_hub.location_id,
            "actor_name": ACTORS["dispatch"],
            "event_type": "dispatch",
            "event_timestamp": dispatch_date,
            "notes": f"Dispatched through {carrier}. Shipment: {shipment_code}",
        })

        if is_delivered:

            custody_event_records.append({
                "asset_id": asset.asset_id,
                "shipment_code": shipment_code,
                "from_location_id": transit_hub.location_id,
                "to_location_id": destination.location_id,
                "actor_name": ACTORS["transfer"],
                "event_type": "transfer",
                "event_timestamp": transfer_date,
                "notes": f"Transferred through {carrier}.",
            })

            custody_event_records.append({
                "asset_id": asset.asset_id,
                "shipment_code": shipment_code,
                "from_location_id": destination.location_id,
                "to_location_id": destination.location_id,
                "actor_name": ACTORS["receipt"],
                "event_type": "receipt",
                "event_timestamp": receipt_date,
                "notes": "Asset received and checked into warehouse.",
            })

    custody_event_records.sort(
        key=lambda event: event["event_timestamp"]
    )

    return shipment_records, custody_event_records


def bulk_insert_shipments_and_events(
    db: Session,
    shipments: list[dict[str, Any]],
    events: list[dict[str, Any]],
    batch_size: int = 2000,
) -> None:

    if not shipments:
        print("No new shipments to insert.")
        return

    try:
        for start in range(0, len(shipments), batch_size):
            chunk = shipments[start:start + batch_size]

            db.add_all([
                Shipment(**record)
                for record in chunk
            ])

        db.flush()

        shipment_codes = [
            record["shipment_code"]
            for record in shipments
        ]

        shipment_ids = {
            shipment.shipment_code: shipment.shipment_id
            for shipment in db.query(Shipment).filter(
                Shipment.shipment_code.in_(shipment_codes)
            ).all()
        }

        event_records = []

        for event in events:
            event_data = event.copy()

            shipment_code = event_data.pop("shipment_code")
            event_data["shipment_id"] = shipment_ids[shipment_code]

            event_records.append(event_data)

        for start in range(0, len(event_records), batch_size):
            chunk = event_records[start:start + batch_size]

            db.bulk_insert_mappings(
                CustodyEvent,
                chunk,
            )

        db.commit()

    except Exception:
        db.rollback()
        raise
