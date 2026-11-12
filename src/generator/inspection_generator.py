
import random
from datetime import timedelta

from sqlalchemy.orm import Session

from src.database.models import (
    Inspection,
    ReturnAuthorization,
)
from src.generator.asset_generator import SIMULATION_DATE


PROJECT_SEED = 20261022

INSPECTORS = [
    "Ravi Kumar",
    "Priya Sharma",
    "Arjun Reddy",
    "Sneha Rao",
    "Kiran Patel",
]


def generate_inspections_batch(
    db: Session,
    seed: int = PROJECT_SEED,
):
    """
    Generate deterministic inspection records for assets
    with return authorizations.

    All inspected assets are marked as good condition.
    """

    rng = random.Random(seed)

    return_records = (
        db.query(ReturnAuthorization)
        .order_by(ReturnAuthorization.return_id)
        .all()
    )

    existing_asset_ids = {
        asset_id
        for (asset_id,) in db.query(Inspection.asset_id).all()
    }

    inspection_records = []

    for return_record in return_records:

        # Avoid duplicate inspections for the same asset
        if return_record.asset_id in existing_asset_ids:
            continue

        # All assets are in good condition
        condition = "good"

        # Generate inspection date after return request
        inspection_date = (
            return_record.request_date
            + timedelta(days=rng.randint(1, 7))
        )

        # Do not exceed simulation date
        if inspection_date > SIMULATION_DATE:
            inspection_date = SIMULATION_DATE

        remarks = "Asset inspected and found in good condition."

        inspection_records.append({
            "asset_id": return_record.asset_id,
            "return_id": return_record.return_id,
            "inspector_name": rng.choice(INSPECTORS),
            "inspection_date": inspection_date,
            "condition_status": condition,
            "remarks": remarks,
        })

        existing_asset_ids.add(return_record.asset_id)

    return inspection_records


def bulk_insert_inspections(
    db: Session,
    records: list,
    batch_size: int = 2000,
):
    """
    Insert inspection records into the database
    using batch insertion.
    """

    if not records:
        print("No new inspection records found.")
        return

    try:
        for start in range(0, len(records), batch_size):

            batch = records[start:start + batch_size]

            db.bulk_insert_mappings(
                Inspection,
                batch,
            )

        db.commit()

    except Exception:
        db.rollback()
        raise
