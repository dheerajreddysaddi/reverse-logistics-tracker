
"""
Synthetic reusable asset generation engine.

Generates deterministic asset records using the existing
SQLAlchemy database models.
"""

import random

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.database.models import AssetType, Owner, ReusableAsset
from src.generator.id_generator import (
    generate_asset_id,
    generate_serial_number,
)


PROJECT_SEED = 20261022

# Fixed simulation date for reproducibility
SIMULATION_DATE = datetime(2026, 10, 22, 23, 59, 59)

# Asset lifecycle statuses and their relative probabilities
STATUS_OPTIONS = [
    "available",
    "in_transit",
    "in_use",
    "under_repair",
    "lost",
    "retired",
]

STATUS_WEIGHTS = [25, 10, 40, 8, 7, 10]


def generate_assets_batch(
    db: Session,
    count: int = 500,
    seed: int = PROJECT_SEED,
) -> list[dict[str, Any]]:
    """
    Generate deterministic reusable asset records.

    The returned records are ready for database insertion.
    """

    if count <= 0:
        raise ValueError("Asset count must be greater than zero.")

    rng = random.Random(seed)

    # Fetch active asset types and owners
    asset_types = (
        db.query(AssetType)
        .filter(AssetType.is_active.is_(True))
        .order_by(AssetType.asset_type_id)
        .all()
    )

    owners = (
        db.query(Owner)
        .filter(Owner.is_active.is_(True))
        .order_by(Owner.owner_id)
        .all()
    )

    if not asset_types:
        raise ValueError(
            "No active asset types found. Run seed_master first."
        )

    if not owners:
        raise ValueError(
            "No active owners found. Run seed_master first."
        )

    asset_records = []

    for index in range(1, count + 1):

        asset_type = rng.choice(asset_types)
        owner = rng.choice(owners)

        asset_code = generate_asset_id(index)

        serial_number = generate_serial_number(
            asset_type.type_name,
            index,
        )

        lifecycle_status = rng.choices(
            STATUS_OPTIONS,
            weights=STATUS_WEIGHTS,
            k=1,
        )[0]

        # Generate a manufacture date between 2023 and 2026.
        start_date = date(2023, 1, 1)
        end_date = date(2026, 7, 1)

        total_days = (end_date - start_date).days

        manufacture_date = (
            start_date + timedelta(days=rng.randint(0, total_days))
        )

        # Creation timestamp must not precede manufacture.
        manufacture_datetime = datetime.combine(
            manufacture_date,
            time(8, 0),
        )

        available_seconds = int(
            (SIMULATION_DATE - manufacture_datetime).total_seconds()
        )

        created_at = manufacture_datetime + timedelta(
            seconds=rng.randint(0, available_seconds)
        )

        asset_records.append(
            {
                "asset_code": asset_code,
                "asset_type_id": asset_type.asset_type_id,
                "owner_id": owner.owner_id,
                "serial_number": serial_number,
                "manufacture_date": manufacture_date,
                "lifecycle_status": lifecycle_status,
                "created_at": created_at,
            }
        )

    return asset_records


def bulk_insert_assets(
    db: Session,
    asset_records: list[dict[str, Any]],
    batch_size: int = 2000,
) -> None:
    """
    Insert asset records into SQLite in batches.

    All batches are committed together so that a failure
    does not leave a partially inserted dataset.
    """

    if batch_size <= 0:
        raise ValueError("Batch size must be greater than zero.")

    try:
        for start in range(0, len(asset_records), batch_size):
            chunk = asset_records[start:start + batch_size]

            db.bulk_insert_mappings(
                ReusableAsset,
                chunk,
            )

        db.commit()

    except Exception:
        db.rollback()
        raise
