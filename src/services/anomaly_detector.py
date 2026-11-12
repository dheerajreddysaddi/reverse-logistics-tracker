
"""
Stage 6: Business Rules and Anomaly Detection Engine.
Detects five mandatory reverse-logistics anomalies.
"""

import math
from collections import defaultdict

from sqlalchemy.orm import Session

from src.database.models import (
    ReusableAsset,
    AssetType,
    Location,
    Shipment,
    CustodyEvent,
    Inspection,
    DepositLedger,
)


# Approximate coordinates of the actual project locations.
LOCATION_COORDINATES = {
    "hyderabad": (17.3850, 78.4867),
    "bengaluru": (12.9716, 77.5946),
    "mumbai": (19.0760, 72.8777),
    "chennai": (13.0827, 80.2707),
}


def haversine_distance_miles(coord1, coord2):
    lat1, lon1 = map(math.radians, coord1)
    lat2, lon2 = map(math.radians, coord2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.asin(math.sqrt(a))

    return 3958.8 * c


class AnomalyDetector:

    @staticmethod
    def detect_impossible_travel(
        db: Session,
        max_speed_mph: float = 600.0,
    ):
        """Rule 1: Detect physically impossible asset travel."""

        anomalies = []

        locations = {
            location.location_id: location
            for location in db.query(Location).all()
        }

        events = (
            db.query(CustodyEvent)
            .filter(CustodyEvent.event_type == "transfer")
            .order_by(
                CustodyEvent.asset_id,
                CustodyEvent.event_timestamp,
                CustodyEvent.event_id,
            )
            .all()
        )

        asset_events = defaultdict(list)

        for event in events:
            asset_events[event.asset_id].append(event)

        for asset_id, history in asset_events.items():

            for index in range(len(history) - 1):

                first = history[index]
                second = history[index + 1]

                location1 = locations.get(first.to_location_id)
                location2 = locations.get(second.to_location_id)

                if not location1 or not location2:
                    continue

                coord1 = LOCATION_COORDINATES.get(
                    (location1.city or "").lower()
                )

                coord2 = LOCATION_COORDINATES.get(
                    (location2.city or "").lower()
                )

                if not coord1 or not coord2:
                    continue

                distance = haversine_distance_miles(
                    coord1,
                    coord2,
                )

                time_hours = (
                    second.event_timestamp - first.event_timestamp
                ).total_seconds() / 3600

                if time_hours <= 0:
                    continue

                speed = distance / time_hours

                if speed > max_speed_mph:

                    anomalies.append({
                        "rule_code": "ANOM-01",
                        "rule_name": "Impossible Travel (Teleportation)",
                        "asset_id": asset_id,
                        "severity": "CRITICAL",
                        "details": (
                            f"Asset travelled {distance:.1f} miles "
                            f"in {time_hours * 60:.1f} minutes "
                            f"at {speed:.0f} mph between "
                            f"{location1.city} and {location2.city}."
                        ),
                    })

        return anomalies

    @staticmethod
    def detect_orphaned_scans(db: Session):
        """Rule 2: Detect receipt events without a shipment."""

        anomalies = (
            db.query(CustodyEvent)
            .filter(
                CustodyEvent.event_type == "receipt",
                CustodyEvent.shipment_id.is_(None),
            )
            .all()
        )

        return [
            {
                "rule_code": "ANOM-02",
                "rule_name": "Orphaned Intake Scan",
                "asset_id": event.asset_id,
                "severity": "HIGH",
                "details": (
                    f"Receipt event {event.event_id} occurred "
                    "without an associated shipment."
                ),
            }
            for event in anomalies
        ]

    @staticmethod
    def detect_premature_refunds(db: Session):
        """Rule 3: Detect refunds before inspection."""

        anomalies = []

        refunds = (
            db.query(DepositLedger)
            .filter(
                DepositLedger.transaction_type == "refund"
            )
            .all()
        )

        for ledger in refunds:

            inspection = (
                db.query(Inspection)
                .filter(
                    Inspection.asset_id == ledger.asset_id
                )
                .order_by(Inspection.inspection_date.asc())
                .first()
            )

            if (
                inspection is None
                or ledger.transaction_date < inspection.inspection_date
            ):

                anomalies.append({
                    "rule_code": "ANOM-03",
                    "rule_name": "Premature Deposit Refund",
                    "asset_id": ledger.asset_id,
                    "severity": "HIGH",
                    "details": (
                        f"Refund of {ledger.amount} was processed "
                        "before inspection completion."
                    ),
                })

        return anomalies

    @staticmethod
    def detect_deposit_over_refund(db: Session):
        """Rule 4: Detect refunds exceeding the original deposit."""

        anomalies = []

        asset_types = {
            item.asset_type_id: item
            for item in db.query(AssetType).all()
        }

        assets = db.query(ReusableAsset).all()

        for asset in assets:

            asset_type = asset_types.get(asset.asset_type_id)

            if asset_type is None:
                continue

            original_deposit = float(
                asset_type.deposit_amount or 0
            )

            if original_deposit <= 0:
                continue

            total_refunded = (
                db.query(DepositLedger)
                .filter(
                    DepositLedger.asset_id == asset.asset_id,
                    DepositLedger.transaction_type == "refund",
                )
                .with_entities(
                    __import__("sqlalchemy").func.sum(
                        DepositLedger.amount
                    )
                )
                .scalar()
                or 0
            )

            if float(total_refunded) > original_deposit:

                anomalies.append({
                    "rule_code": "ANOM-04",
                    "rule_name": "Deposit Over-Refund (Ledger Deficit)",
                    "asset_id": asset.asset_id,
                    "severity": "CRITICAL",
                    "details": (
                        f"Total refunded: {total_refunded}; "
                        f"Original deposit: {original_deposit}."
                    ),
                })

        return anomalies

    @staticmethod
    def detect_double_custody(db: Session):
        """Rule 5: Detect assets assigned to multiple active shipments."""

        anomalies = []

        active_shipments = (
            db.query(Shipment)
            .filter(
                Shipment.shipment_status.in_(
                    ["planned", "dispatched"]
                )
            )
            .all()
        )

        asset_shipments = defaultdict(set)

        for shipment in active_shipments:

            events = (
                db.query(CustodyEvent)
                .filter(
                    CustodyEvent.shipment_id == shipment.shipment_id
                )
                .all()
            )

            for event in events:
                asset_shipments[event.asset_id].add(
                    shipment.shipment_id
                )

        for asset_id, shipment_ids in asset_shipments.items():

            if len(shipment_ids) > 1:

                anomalies.append({
                    "rule_code": "ANOM-05",
                    "rule_name": "Double Custody (Concurrent Shipments)",
                    "asset_id": asset_id,
                    "severity": "CRITICAL",
                    "details": (
                        f"Asset is assigned to {len(shipment_ids)} "
                        f"active shipments: {sorted(shipment_ids)}."
                    ),
                })

        return anomalies

    @classmethod
    def scan_all(cls, db: Session):
        """Run all five anomaly detection rules."""

        results = []

        results.extend(cls.detect_impossible_travel(db))
        results.extend(cls.detect_orphaned_scans(db))
        results.extend(cls.detect_premature_refunds(db))
        results.extend(cls.detect_deposit_over_refund(db))
        results.extend(cls.detect_double_custody(db))

        return results
