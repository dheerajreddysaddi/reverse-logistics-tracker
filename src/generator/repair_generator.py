
import random
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from src.database.models import (
    Inspection,
    Repair,
)
from src.generator.asset_generator import SIMULATION_DATE
from src.generator.id_generator import generate_repair_code


PROJECT_SEED = 20261022

REPAIR_DETAILS = [
    ("Cleaning and surface restoration", Decimal("250.00")),
    ("Minor component replacement", Decimal("500.00")),
    ("Structural repair and reinforcement", Decimal("1200.00")),
    ("Complete refurbishment", Decimal("2500.00")),
]


def generate_repairs_batch(
    db: Session,
    seed: int = PROJECT_SEED,
):
    """
    Generate repair records only for damaged or unusable assets.
    """

    rng = random.Random(seed)

    inspections = (
        db.query(Inspection)
        .filter(
            Inspection.condition_status.in_(
                ["damaged", "unusable"]
            )
        )
        .order_by(Inspection.inspection_id)
        .all()
    )

    existing_inspection_ids = {
        inspection_id
        for (inspection_id,) in db.query(
            Repair.inspection_id
        ).all()
    }

    repair_records = []

    for idx, inspection in enumerate(inspections, start=len(existing_inspection_ids) + 1):

        if inspection.inspection_id in existing_inspection_ids:
            continue

        description, cost = rng.choice(REPAIR_DETAILS)

        opened_at = inspection.inspection_date

        repair_status = rng.choice(
            ["open", "in_progress", "completed"]
        )

        closed_at = None

        if repair_status == "completed":
            closed_at = opened_at + timedelta(
                days=rng.randint(1, 10)
            )

            if closed_at > SIMULATION_DATE:
                closed_at = SIMULATION_DATE

        repair_records.append({
            "repair_code": generate_repair_code(idx),
            "asset_id": inspection.asset_id,
            "inspection_id": inspection.inspection_id,
            "repair_description": description,
            "repair_cost": cost,
            "repair_status": repair_status,
            "opened_at": opened_at,
            "closed_at": closed_at,
        })

        existing_inspection_ids.add(
            inspection.inspection_id
        )

    return repair_records


def bulk_insert_repairs(
    db: Session,
    records: list,
    batch_size: int = 2000,
):
    """Insert repair records into the database in batches."""

    if not records:
        print("No repair records required. All inspections are good.")
        return

    try:
        for start in range(0, len(records), batch_size):

            batch = records[start:start + batch_size]

            db.bulk_insert_mappings(
                Repair,
                batch,
            )

        db.commit()

    except Exception:
        db.rollback()
        raise
