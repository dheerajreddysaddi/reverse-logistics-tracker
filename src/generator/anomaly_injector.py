"""
Stage 6: Controlled Anomaly Injector.

Creates exactly two deterministic test cases for each of the five mandatory rules:
1. MULTIPLE_ACTIVE_LOCATIONS: Asset detected at multiple active locations / impossible travel.
2. RETURN_BEFORE_DISPATCH: Return processed before original shipment dispatch.
3. DUPLICATE_REFUND: Multiple refunds for the same deposit or excessive refund.
4. REPAIR_WITHOUT_INSPECTION: Repair completed without a valid inspection record.
5. MISSING_CUSTODY_ACTOR: Custody scan recorded without an authorized actor.

Uses separate assets for each case and preserves existing project records.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from src.database.models import (
    ReusableAsset,
    AssetType,
    Location,
    Shipment,
    CustodyEvent,
    Inspection,
    Repair,
    ReturnAuthorization,
    DepositLedger,
)
from src.generator.id_generator import (
    generate_custody_event_id,
    generate_repair_code,
    generate_rma_number,
)


def inject_mandatory_edge_cases(db):
    """
    Injects 10 deterministic anomalies (exactly 2 for each of the 5 rules)
    across 10 separate assets.
    """
    # Prevent duplicate injection when the runner is executed again.
    already_injected = (
        db.query(CustodyEvent)
        .filter(CustodyEvent.notes.like("STAGE6:%"))
        .first()
    )

    if already_injected:
        print("Stage 6 anomalies have already been injected.")
        return []

    # Find locations
    locations = {
        location.city.lower(): location
        for location in db.query(Location).all()
    }

    required_cities = ["hyderabad", "chennai", "mumbai"]
    for city in required_cities:
        if city not in locations:
            raise ValueError(f"Required location not found: {city}")

    hyderabad = locations["hyderabad"]
    chennai = locations["chennai"]
    mumbai = locations["mumbai"]

    # Exclude assets already used in custody, inspections or ledgers.
    used_ids = set()
    for model in [CustodyEvent, Inspection, DepositLedger, Repair, ReturnAuthorization]:
        used_ids.update(
            row[0]
            for row in db.query(model.asset_id).distinct().all()
        )

    asset_types = {
        item.asset_type_id: item
        for item in db.query(AssetType).all()
    }

    candidates = []
    for asset in (
        db.query(ReusableAsset)
        .order_by(ReusableAsset.asset_id)
        .all()
    ):
        if asset.asset_id in used_ids:
            continue
        asset_type = asset_types.get(asset.asset_type_id)
        if asset_type is None or not asset_type.deposit_amount or asset_type.deposit_amount <= 0:
            continue
        candidates.append((asset, asset_type))

    if len(candidates) < 10:
        raise ValueError(
            f"Need 10 unused assets, but found {len(candidates)}."
        )

    # Exactly ten different assets: two for each rule.
    selected = candidates[:10]
    ground_truth = []
    base_time = datetime(2026, 10, 20, 10, 0, 0)

    try:
        # -------------------------------------------------
        # RULE 1: MULTIPLE_ACTIVE_LOCATIONS (ANOM-01)
        # Chennai to Mumbai (642 miles) in 20 minutes (>1900 mph).
        # -------------------------------------------------
        for index, (asset, asset_type) in enumerate(selected[0:2]):
            first_time = base_time + timedelta(minutes=index * 60)
            second_time = first_time + timedelta(minutes=20)

            db.add_all([
                CustodyEvent(
                    asset_id=asset.asset_id,
                    event_code=generate_custody_event_id(asset.asset_code, 1),
                    shipment_id=None,
                    from_location_id=hyderabad.location_id,
                    to_location_id=chennai.location_id,
                    actor_name="Stage 6 Scanner Chennai",
                    event_type="transfer",
                    event_timestamp=first_time,
                    notes="STAGE6:ANOM-01 first location scan",
                ),
                CustodyEvent(
                    asset_id=asset.asset_id,
                    event_code=generate_custody_event_id(asset.asset_code, 2),
                    shipment_id=None,
                    from_location_id=chennai.location_id,
                    to_location_id=mumbai.location_id,
                    actor_name="Stage 6 Scanner Mumbai",
                    event_type="transfer",
                    event_timestamp=second_time,
                    notes="STAGE6:ANOM-01 impossible travel scan",
                ),
            ])

            ground_truth.append({
                "asset_id": asset.asset_id,
                "rule_code": "ANOM-01",
                "issue_type": "MULTIPLE_ACTIVE_LOCATIONS",
                "rule_name": "Multiple Active Locations (Impossible Travel)",
            })

        # -------------------------------------------------
        # RULE 2: RETURN_BEFORE_DISPATCH (ANOM-02)
        # Return intake event occurs before original shipment dispatch.
        # -------------------------------------------------
        for index, (asset, asset_type) in enumerate(selected[2:4]):
            dispatch_time = base_time + timedelta(days=1, hours=10)
            premature_return_time = dispatch_time - timedelta(hours=5)

            # Create shipment
            shipment = Shipment(
                shipment_code=f"SHP-2026-STAGE6-{asset.asset_code}",
                origin_location_id=chennai.location_id,
                destination_location_id=hyderabad.location_id,
                carrier_name="Apex Freight",
                dispatch_date=dispatch_time,
                expected_delivery_date=dispatch_time + timedelta(days=3),
                actual_delivery_date=None,
                shipment_status="dispatched",
            )
            db.add(shipment)
            db.flush()

            # Return authorization dated before dispatch
            rma = ReturnAuthorization(
                return_code=f"RMA-2026-STAGE6-{asset.asset_code}",
                asset_id=asset.asset_id,
                shipment_id=shipment.shipment_id,
                requested_by="Stage 6 Premature Receiver",
                request_date=premature_return_time,
                approved_date=premature_return_time,
                return_status="requested",
            )
            db.add(rma)

            db.add(
                CustodyEvent(
                    asset_id=asset.asset_id,
                    event_code=generate_custody_event_id(asset.asset_code, 1),
                    shipment_id=shipment.shipment_id,
                    from_location_id=chennai.location_id,
                    to_location_id=hyderabad.location_id,
                    actor_name="Stage 6 Dock Receiver",
                    event_type="return",
                    event_timestamp=premature_return_time,
                    notes="STAGE6:ANOM-02 return before dispatch",
                )
            )

            ground_truth.append({
                "asset_id": asset.asset_id,
                "rule_code": "ANOM-02",
                "issue_type": "RETURN_BEFORE_DISPATCH",
                "rule_name": "Return Processed Before Dispatch",
            })

        # -------------------------------------------------
        # RULE 3: DUPLICATE_REFUND (ANOM-03)
        # Two duplicate refund transactions for the same deposit.
        # -------------------------------------------------
        for index, (asset, asset_type) in enumerate(selected[4:6]):
            deposit = Decimal(str(asset_type.deposit_amount))
            refund_amount = (deposit * Decimal("0.50")).quantize(Decimal("0.01"))
            tx_time = base_time + timedelta(days=2, minutes=index * 30)

            # Initial deposit charge
            db.add(
                DepositLedger(
                    asset_id=asset.asset_id,
                    shipment_id=None,
                    transaction_type="charge",
                    amount=deposit,
                    transaction_date=tx_time - timedelta(days=5),
                    reference_code=f"CHG-STAGE6-{asset.asset_code}",
                    notes="STAGE6: Initial security deposit charge",
                )
            )

            # First refund
            db.add(
                DepositLedger(
                    asset_id=asset.asset_id,
                    shipment_id=None,
                    transaction_type="refund",
                    amount=refund_amount,
                    transaction_date=tx_time,
                    reference_code=f"REF-STAGE6-A-{asset.asset_code}",
                    notes="STAGE6:ANOM-03 first refund transaction",
                )
            )

            # Duplicate refund of same amount
            db.add(
                DepositLedger(
                    asset_id=asset.asset_id,
                    shipment_id=None,
                    transaction_type="refund",
                    amount=refund_amount,
                    transaction_date=tx_time + timedelta(hours=1),
                    reference_code=f"REF-STAGE6-B-{asset.asset_code}",
                    notes="STAGE6:ANOM-03 duplicate refund transaction",
                )
            )

            ground_truth.append({
                "asset_id": asset.asset_id,
                "rule_code": "ANOM-03",
                "issue_type": "DUPLICATE_REFUND",
                "rule_name": "Duplicate Deposit Refund",
            })

        # -------------------------------------------------
        # RULE 4: REPAIR_WITHOUT_INSPECTION (ANOM-04)
        # Repair closed without a preceding diagnostic inspection.
        # -------------------------------------------------
        for index, (asset, asset_type) in enumerate(selected[6:8]):
            repair_time = base_time + timedelta(days=3, hours=index)

            db.add(
                Repair(
                    repair_code=generate_repair_code(9000 + index),
                    asset_id=asset.asset_id,
                    inspection_id=None,
                    repair_description="STAGE6:ANOM-04 repair without inspection: structural overhaul closed without diagnostic assessment",
                    repair_cost=Decimal("1850.00"),
                    repair_status="completed",
                    opened_at=repair_time,
                    closed_at=repair_time + timedelta(days=2),
                )
            )

            ground_truth.append({
                "asset_id": asset.asset_id,
                "rule_code": "ANOM-04",
                "issue_type": "REPAIR_WITHOUT_INSPECTION",
                "rule_name": "Repair Closed Without Inspection",
            })

        # -------------------------------------------------
        # RULE 5: MISSING_CUSTODY_ACTOR (ANOM-05)
        # Custody event recorded with missing or invalid actor name.
        # -------------------------------------------------
        for index, (asset, asset_type) in enumerate(selected[8:10]):
            event_time = base_time + timedelta(days=4, minutes=index * 45)

            db.add(
                CustodyEvent(
                    asset_id=asset.asset_id,
                    event_code=generate_custody_event_id(asset.asset_code, 1),
                    shipment_id=None,
                    from_location_id=hyderabad.location_id,
                    to_location_id=chennai.location_id,
                    actor_name="UNKNOWN_ACTOR",
                    event_type="transfer",
                    event_timestamp=event_time,
                    notes="STAGE6:ANOM-05 missing custody actor",
                )
            )

            ground_truth.append({
                "asset_id": asset.asset_id,
                "rule_code": "ANOM-05",
                "issue_type": "MISSING_CUSTODY_ACTOR",
                "rule_name": "Missing Custody Actor",
            })

        db.commit()
        print("Controlled anomalies (all 5 mandatory rules) committed successfully.")
        return ground_truth

    except Exception:
        db.rollback()
        raise
