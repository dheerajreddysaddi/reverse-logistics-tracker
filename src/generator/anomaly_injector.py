
"""
Stage 6: Controlled Anomaly Injector.

Creates two test cases for each of the five mandatory rules.
Uses separate assets and preserves existing project records.
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
    DepositLedger,
)


def inject_mandatory_edge_cases(db):

    # Prevent duplicate injection when the runner is executed again.
    already_injected = (
        db.query(CustodyEvent)
        .filter(
            CustodyEvent.notes.like("STAGE6:%")
        )
        .first()
    )

    if already_injected:
        print("Stage 6 anomalies have already been injected.")
        return []

    # Find the real locations.
    locations = {
        location.city.lower(): location
        for location in db.query(Location).all()
    }

    required_cities = [
        "hyderabad",
        "chennai",
        "mumbai",
    ]

    for city in required_cities:
        if city not in locations:
            raise ValueError(
                f"Required location not found: {city}"
            )

    hyderabad = locations["hyderabad"]
    chennai = locations["chennai"]
    mumbai = locations["mumbai"]

    # Exclude assets already used in custody, inspections or ledgers.
    used_ids = set()

    for model in [CustodyEvent, Inspection, DepositLedger]:
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

        if asset_type is None:
            continue

        if not asset_type.deposit_amount or asset_type.deposit_amount <= 0:
            continue

        candidates.append((asset, asset_type))

    if len(candidates) < 10:
        raise ValueError(
            f"Need 10 unused assets, but found {len(candidates)}."
        )

    # Ten different assets: two for each rule.
    selected = candidates[:10]

    ground_truth = []

    base_time = datetime(2026, 10, 20, 10, 0, 0)

    try:

        # -------------------------------------------------
        # RULE 1: IMPOSSIBLE TRAVEL
        # Chennai to Mumbai in 20 minutes.
        # -------------------------------------------------

        for index, (asset, asset_type) in enumerate(selected[0:2]):

            first_time = base_time + timedelta(minutes=index * 60)
            second_time = first_time + timedelta(minutes=20)

            db.add_all([
                CustodyEvent(
                    asset_id=asset.asset_id,
                    shipment_id=None,
                    from_location_id=hyderabad.location_id,
                    to_location_id=chennai.location_id,
                    actor_name="Stage 6 Test Scanner Chennai",
                    event_type="transfer",
                    event_timestamp=first_time,
                    notes="STAGE6:ANOM-01 first location scan",
                ),
                CustodyEvent(
                    asset_id=asset.asset_id,
                    shipment_id=None,
                    from_location_id=chennai.location_id,
                    to_location_id=mumbai.location_id,
                    actor_name="Stage 6 Test Scanner Mumbai",
                    event_type="transfer",
                    event_timestamp=second_time,
                    notes="STAGE6:ANOM-01 impossible travel scan",
                ),
            ])

            ground_truth.append({
                "asset_id": asset.asset_id,
                "rule_code": "ANOM-01",
                "rule_name": "Impossible Travel",
            })

        # -------------------------------------------------
        # RULE 2: ORPHANED RECEIPT WITHOUT SHIPMENT
        # -------------------------------------------------

        for index, (asset, asset_type) in enumerate(selected[2:4]):

            db.add(
                CustodyEvent(
                    asset_id=asset.asset_id,
                    shipment_id=None,
                    from_location_id=chennai.location_id,
                    to_location_id=hyderabad.location_id,
                    actor_name="Stage 6 Orphaned Dock Receiver",
                    event_type="receipt",
                    event_timestamp=base_time + timedelta(days=1, minutes=index),
                    notes="STAGE6:ANOM-02 receipt without shipment",
                )
            )

            ground_truth.append({
                "asset_id": asset.asset_id,
                "rule_code": "ANOM-02",
                "rule_name": "Orphaned Intake Scan",
            })

        # -------------------------------------------------
        # RULE 3: PREMATURE DEPOSIT REFUND
        # No inspection exists for these assets.
        # -------------------------------------------------

        for index, (asset, asset_type) in enumerate(selected[4:6]):

            deposit = Decimal(str(asset_type.deposit_amount))

            refund_amount = (deposit * Decimal("0.25")).quantize(
                Decimal("0.01")
            )

            db.add(
                DepositLedger(
                    asset_id=asset.asset_id,
                    shipment_id=None,
                    transaction_type="refund",
                    amount=refund_amount,
                    transaction_date=base_time + timedelta(days=2, minutes=index),
                    reference_code=f"STAGE6-ANOM-03-{asset.asset_code}",
                    notes="STAGE6:ANOM-03 refund issued before inspection",
                )
            )

            ground_truth.append({
                "asset_id": asset.asset_id,
                "rule_code": "ANOM-03",
                "rule_name": "Premature Deposit Refund",
            })

        # -------------------------------------------------
        # RULE 4: DEPOSIT OVER-REFUND
        # Create a valid earlier inspection, then excessive refund.
        # -------------------------------------------------

        for index, (asset, asset_type) in enumerate(selected[6:8]):

            deposit = Decimal(str(asset_type.deposit_amount))

            inspection_time = base_time + timedelta(days=2)

            db.add(
                Inspection(
                    asset_id=asset.asset_id,
                    return_id=None,
                    inspector_name="Stage 6 Baseline Inspector",
                    inspection_date=inspection_time,
                    condition_status="good",
                    remarks="STAGE6: baseline inspection before refund",
                )
            )

            db.add(
                DepositLedger(
                    asset_id=asset.asset_id,
                    shipment_id=None,
                    transaction_type="refund",
                    amount=deposit + Decimal("350.00"),
                    transaction_date=inspection_time + timedelta(days=1),
                    reference_code=f"STAGE6-ANOM-04-{asset.asset_code}",
                    notes="STAGE6:ANOM-04 refund exceeds original deposit",
                )
            )

            ground_truth.append({
                "asset_id": asset.asset_id,
                "rule_code": "ANOM-04",
                "rule_name": "Deposit Over-Refund",
            })

        # -------------------------------------------------
        # RULE 5: DOUBLE CUSTODY
        # Two active shipments for the same asset.
        # -------------------------------------------------

        for index, (asset, asset_type) in enumerate(selected[8:10]):

            dispatch_time = base_time + timedelta(days=2, hours=3, minutes=index * 60)

            shipment_a = Shipment(
                shipment_code=f"SHP-STAGE6-{asset.asset_code}-A",
                origin_location_id=hyderabad.location_id,
                destination_location_id=chennai.location_id,
                carrier_name="Stage 6 Test Carrier A",
                dispatch_date=dispatch_time,
                expected_delivery_date=dispatch_time + timedelta(days=2),
                actual_delivery_date=None,
                shipment_status="dispatched",
            )

            shipment_b = Shipment(
                shipment_code=f"SHP-STAGE6-{asset.asset_code}-B",
                origin_location_id=hyderabad.location_id,
                destination_location_id=mumbai.location_id,
                carrier_name="Stage 6 Test Carrier B",
                dispatch_date=dispatch_time + timedelta(minutes=30),
                expected_delivery_date=dispatch_time + timedelta(days=3),
                actual_delivery_date=None,
                shipment_status="dispatched",
            )

            db.add_all([shipment_a, shipment_b])
            db.flush()

            db.add_all([
                CustodyEvent(
                    asset_id=asset.asset_id,
                    shipment_id=shipment_a.shipment_id,
                    from_location_id=hyderabad.location_id,
                    to_location_id=chennai.location_id,
                    actor_name="Stage 6 Dispatch Clerk A",
                    event_type="dispatch",
                    event_timestamp=dispatch_time,
                    notes="STAGE6:ANOM-05 first concurrent shipment",
                ),
                CustodyEvent(
                    asset_id=asset.asset_id,
                    shipment_id=shipment_b.shipment_id,
                    from_location_id=hyderabad.location_id,
                    to_location_id=mumbai.location_id,
                    actor_name="Stage 6 Dispatch Clerk B",
                    event_type="dispatch",
                    event_timestamp=dispatch_time + timedelta(minutes=30),
                    notes="STAGE6:ANOM-05 second concurrent shipment",
                ),
            ])

            ground_truth.append({
                "asset_id": asset.asset_id,
                "rule_code": "ANOM-05",
                "rule_name": "Double Custody",
            })

        db.commit()

        print("Controlled anomalies committed successfully.")

        return ground_truth

    except Exception:
        db.rollback()
        raise
