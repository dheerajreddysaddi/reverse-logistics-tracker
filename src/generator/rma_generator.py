
"""
Stage 5: Reverse Logistics Generator.
Generates RMAs, inspections, repairs and deposit ledger entries.
"""

import random
import re

from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from src.database.models import (
    AssetType,
    ReusableAsset,
    Shipment,
    CustodyEvent,
    ReturnAuthorization,
    Inspection,
    Repair,
    DepositLedger,
)

from src.services.reverse_logistics_service import ReverseLogisticsService
from src.generator.id_generator import generate_repair_code


INSPECTORS = [
    "Arjun Reddy",
    "Priya Sharma",
    "Rahul Kumar",
    "Ananya Rao",
]


def generate_reverse_logistics_batch(
    db: Session,
    return_count: int = 100,
    seed: int = 42,
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
]:

    rng = random.Random(seed)

    # Find delivered assets with receipt events.
    delivered_events = (
        db.query(CustodyEvent, Shipment)
        .join(
            Shipment,
            CustodyEvent.shipment_id == Shipment.shipment_id,
        )
        .filter(
            Shipment.shipment_status == "delivered",
            CustodyEvent.event_type == "receipt",
        )
        .order_by(CustodyEvent.event_timestamp.asc())
        .all()
    )

    # Exclude assets that already have RMAs.
    existing_asset_ids = {
        row[0]
        for row in db.query(
            ReturnAuthorization.asset_id
        ).distinct().all()
    }

    assets = {
        asset.asset_id: asset
        for asset in db.query(ReusableAsset).all()
    }

    asset_types = {
        item.asset_type_id: item
        for item in db.query(AssetType).all()
    }

    candidates = []
    used_asset_ids = set()

    for event, shipment in delivered_events:

        asset_id = event.asset_id

        if asset_id in existing_asset_ids:
            continue

        if asset_id in used_asset_ids:
            continue

        asset = assets.get(asset_id)

        if asset is None:
            continue

        asset_type = asset_types.get(asset.asset_type_id)

        if asset_type is None:
            continue

        candidates.append(
            (asset, asset_type, shipment, event)
        )

        used_asset_ids.add(asset_id)

    actual_count = min(return_count, len(candidates))

    if actual_count == 0:
        print("No eligible assets found.")
        return [], [], [], []

    # Continue RMA numbering from existing records.
    existing_codes = [
        row[0]
        for row in db.query(
            ReturnAuthorization.return_code
        ).all()
    ]

    highest_number = 0

    for code in existing_codes:
        match = re.search(r"(\d+)$", code or "")

        if match:
            highest_number = max(
                highest_number,
                int(match.group(1))
            )

    rma_records = []
    inspection_records = []
    repair_records = []
    ledger_records = []

    for index in range(actual_count):

        asset, asset_type, shipment, event = candidates[index]

        request_date = event.event_timestamp + timedelta(
            days=rng.randint(1, 3)
        )

        return_code = (
            f"RMA-{request_date.year}-"
            f"{highest_number + index + 1:06d}"
        )

        # RMA record.
        rma_records.append({
            "return_code": return_code,
            "asset_id": asset.asset_id,
            "shipment_id": shipment.shipment_id,
            "requested_by": rng.choice(INSPECTORS),
            "request_date": request_date,
            "approved_date": request_date + timedelta(days=1),
            "return_status": "received",
        })

        # Inspection scores.
        cosmetic = rng.choices(
            [10, 9, 8, 6, 3],
            weights=[35, 30, 20, 10, 5],
        )[0]

        functional = rng.choices(
            [10, 9, 8, 5, 2],
            weights=[40, 30, 15, 10, 5],
        )[0]

        grade, condition, action = (
            ReverseLogisticsService.evaluate_inspection(
                cosmetic,
                functional,
            )
        )

        inspected_at = request_date + timedelta(
            days=rng.randint(2, 5)
        )

        inspection_records.append({
            "_return_code": return_code,
            "asset_id": asset.asset_id,
            "inspector_name": rng.choice(INSPECTORS),
            "inspection_date": inspected_at,
            "condition_status": condition,
            "remarks": (
                f"Grade {grade}; "
                f"Cosmetic score: {cosmetic}/10; "
                f"Functional score: {functional}/10; "
                f"Recommended action: {action}."
            ),
        })

        # Repair for Grade C.
        if action == "refurbish":

            opened_at = inspected_at + timedelta(days=1)

            closed_at = opened_at + timedelta(
                days=rng.randint(2, 5)
            )

            repair_records.append({
                "_return_code": return_code,
                "asset_id": asset.asset_id,
                "repair_description": (
                    "Refurbishment completed: damaged components "
                    "replaced and asset tested."
                ),
                "repair_cost": Decimal(
                    str(round(rng.uniform(500, 2500), 2))
                ),
                "repair_status": "completed",
                "opened_at": opened_at,
                "closed_at": closed_at,
            })

        # Deposit settlement.
        deposit = asset_type.deposit_amount or Decimal("0.00")

        transaction_type, amount, note = (
            ReverseLogisticsService.calculate_deposit_settlement(
                deposit,
                grade,
            )
        )

        # Allowed database transaction types:
        # charge, refund, adjustment.
        if transaction_type is not None and amount > 0:

            ledger_records.append({
                "asset_id": asset.asset_id,
                "shipment_id": shipment.shipment_id,
                "transaction_type": transaction_type,
                "amount": amount,
                "transaction_date": inspected_at + timedelta(hours=2),
                "reference_code": return_code,
                "notes": (
                    f"{note} Inspection grade: {grade}. "
                    f"Original deposit: {deposit}."
                ),
            })

    return (
        rma_records,
        inspection_records,
        repair_records,
        ledger_records,
    )


def bulk_insert_reverse_logistics(
    db: Session,
    rmas: List[Dict[str, Any]],
    inspections: List[Dict[str, Any]],
    repairs: List[Dict[str, Any]],
    ledgers: List[Dict[str, Any]],
):

    try:

        if not rmas:
            print("No new records to insert.")
            return

        # Insert RMAs.
        db.bulk_insert_mappings(
            ReturnAuthorization,
            rmas,
        )

        db.flush()

        return_codes = [
            record["return_code"]
            for record in rmas
        ]

        rma_rows = (
            db.query(ReturnAuthorization)
            .filter(
                ReturnAuthorization.return_code.in_(return_codes)
            )
            .all()
        )

        return_id_map = {
            row.return_code: row.return_id
            for row in rma_rows
        }

        # Insert inspections.
        inspection_mappings = []

        for record in inspections:

            return_id = return_id_map[
                record["_return_code"]
            ]

            inspection_mappings.append({
                "asset_id": record["asset_id"],
                "return_id": return_id,
                "inspector_name": record["inspector_name"],
                "inspection_date": record["inspection_date"],
                "condition_status": record["condition_status"],
                "remarks": record["remarks"],
            })

        db.bulk_insert_mappings(
            Inspection,
            inspection_mappings,
        )

        db.flush()

        return_ids = list(return_id_map.values())

        inspection_rows = (
            db.query(Inspection)
            .filter(
                Inspection.return_id.in_(return_ids)
            )
            .all()
        )

        inspection_id_map = {
            row.return_id: row.inspection_id
            for row in inspection_rows
        }

        # Insert repairs.
        existing_repairs = db.query(Repair).count()
        repair_mappings = []

        for idx, record in enumerate(repairs, start=existing_repairs + 1):

            return_id = return_id_map[
                record["_return_code"]
            ]

            repair_mappings.append({
                "repair_code": generate_repair_code(idx),
                "asset_id": record["asset_id"],
                "inspection_id": inspection_id_map[return_id],
                "repair_description": record["repair_description"],
                "repair_cost": record["repair_cost"],
                "repair_status": record["repair_status"],
                "opened_at": record["opened_at"],
                "closed_at": record["closed_at"],
            })

        if repair_mappings:
            db.bulk_insert_mappings(
                Repair,
                repair_mappings,
            )

        # Insert deposit ledger entries.
        if ledgers:
            db.bulk_insert_mappings(
                DepositLedger,
                ledgers,
            )

        db.commit()

        print("Reverse logistics records inserted successfully.")

    except Exception:
        db.rollback()
        raise
