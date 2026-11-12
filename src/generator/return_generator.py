import random
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database.models import (
    Shipment,
    CustodyEvent,
    ReusableAsset,
    ReturnAuthorization,
)
from src.generator.id_generator import generate_rma_number


PROJECT_SEED = 20261022
SIMULATION_DATE = __import__("datetime").datetime(2026, 10, 22, 23, 59, 59)


def generate_return_authorizations_batch(
    db: Session,
    seed: int = PROJECT_SEED,
):
    """
    Generate return authorizations for eligible delivered shipments.
    Only assets with available or in_use status are considered.
    """

    rng = random.Random(seed)

    existing_assets = {
        asset_id
        for (asset_id,) in db.query(
            ReturnAuthorization.asset_id
        ).all()
    }

    existing_shipments = {
        shipment_id
        for (shipment_id,) in db.query(
            ReturnAuthorization.shipment_id
        ).filter(
            ReturnAuthorization.shipment_id.isnot(None)
        ).all()
    }

    existing_codes = {
        code
        for (code,) in db.query(
            ReturnAuthorization.return_code
        ).all()
    }

    rows = (
        db.query(CustodyEvent, Shipment, ReusableAsset)
        .join(
            Shipment,
            CustodyEvent.shipment_id == Shipment.shipment_id,
        )
        .join(
            ReusableAsset,
            CustodyEvent.asset_id == ReusableAsset.asset_id,
        )
        .filter(
            Shipment.shipment_status == "delivered",
            CustodyEvent.event_type == "receipt",
            ReusableAsset.lifecycle_status.in_(
                ["available", "in_use"]
            ),
        )
        .order_by(
            CustodyEvent.event_timestamp,
            Shipment.shipment_id,
        )
        .all()
    )

    max_return_id = (
        db.query(func.max(ReturnAuthorization.return_id)).scalar()
        or 0
    )

    return_records = []
    seen_assets = set()
    seen_shipments = set()

    for receipt_event, shipment, asset in rows:

        if asset.asset_id in existing_assets:
            continue

        if shipment.shipment_id in existing_shipments:
            continue

        if asset.asset_id in seen_assets:
            continue

        if shipment.shipment_id in seen_shipments:
            continue

        index = max_return_id + len(return_records) + 1
        return_code = generate_rma_number(index)

        while return_code in existing_codes:
            index += 1
            return_code = generate_rma_number(index)

        request_date = (
            receipt_event.event_timestamp
            + timedelta(days=rng.randint(1, 30))
        )

        if request_date > SIMULATION_DATE:
            request_date = SIMULATION_DATE

        return_records.append({
            "return_code": return_code,
            "asset_id": asset.asset_id,
            "shipment_id": shipment.shipment_id,
            "requested_by": "Customer Service Portal",
            "request_date": request_date,
            "approved_date": None,
            "return_status": "requested",
        })

        seen_assets.add(asset.asset_id)
        seen_shipments.add(shipment.shipment_id)
        existing_codes.add(return_code)

    return return_records


def bulk_insert_return_authorizations(
    db: Session,
    records: list,
    batch_size: int = 2000,
):
    """Insert return authorization records in batches."""

    if not records:
        print("No eligible return authorizations found.")
        return

    try:
        for start in range(0, len(records), batch_size):
            batch = records[start:start + batch_size]

            db.bulk_insert_mappings(
                ReturnAuthorization,
                batch,
            )

        db.commit()

    except Exception:
        db.rollback()
        raise