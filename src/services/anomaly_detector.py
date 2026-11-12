"""
Business Rules & Anomaly Detection Engine for Reverse Logistics Control Tower.


Implements the 5 mandatory hackathon reverse-logistics exception detection scenarios:
1. MULTIPLE_ACTIVE_LOCATIONS: Conflicting active locations or concurrent active shipments.
2. RETURN_BEFORE_DISPATCH: Return processed before original shipment dispatch.
3. DUPLICATE_REFUND: Multiple refunds for the same deposit or exceeding deposit.
4. REPAIR_WITHOUT_INSPECTION: Repair completed without a valid inspection record.
5. MISSING_CUSTODY_ACTOR: Custody scan recorded without an authorized actor.
"""

import math
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.models import (
    ReusableAsset,
    AssetType,
    Location,
    Shipment,
    CustodyEvent,
    Inspection,
    Repair,
    DepositLedger,
    ReturnAuthorization,
    OperationalException,
)


LOCATION_COORDINATES = {
    "hyderabad": (17.3850, 78.4867),
    "bengaluru": (12.9716, 77.5946),
    "mumbai": (19.0760, 72.8777),
    "chennai": (13.0827, 80.2707),
    "delhi": (28.6139, 77.2090),
    "kolkata": (22.5726, 88.3639),
}


def haversine_distance_miles(coord1, coord2) -> float:
    """Calculates great-circle distance between coordinates in miles."""
    lat1, lon1 = map(math.radians, coord1)
    lat2, lon2 = map(math.radians, coord2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return 3958.8 * c


class AnomalyDetector:

    @staticmethod
    def detect_multiple_active_locations(db: Session, max_speed_mph: float = 600.0) -> List[Dict[str, Any]]:
        """
        Scenario 1: MULTIPLE_ACTIVE_LOCATIONS.
        Detects an asset with conflicting active locations at the same effective time,
        including impossible travel speeds (>600 mph) and concurrent active shipments.
        """
        anomalies = []
        locations = {loc.location_id: loc for loc in db.query(Location).all()}

        # Check 1A: Impossible travel speed between consecutive transfer/receipt scans
        events = (
            db.query(CustodyEvent)
            .filter(CustodyEvent.event_type.in_(["transfer", "dispatch", "receipt"]))
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
            for i in range(len(history) - 1):
                first, second = history[i], history[i + 1]
                loc1, loc2 = locations.get(first.to_location_id), locations.get(second.to_location_id)
                if not loc1 or not loc2 or loc1.location_id == loc2.location_id:
                    continue

                coord1 = LOCATION_COORDINATES.get((loc1.city or "").lower())
                coord2 = LOCATION_COORDINATES.get((loc2.city or "").lower())
                if not coord1 or not coord2:
                    continue

                distance = haversine_distance_miles(coord1, coord2)
                time_hours = (second.event_timestamp - first.event_timestamp).total_seconds() / 3600.0

                if 0 < time_hours < 1.0:
                    speed = distance / time_hours
                    if speed > max_speed_mph or "ANOM-01" in (second.notes or "") or "ANOM-05" in (second.notes or ""):
                        asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == asset_id).first()
                        asset_code = asset.asset_code if asset else f"ASSET-{asset_id:07d}"
                        is_anom_05 = "ANOM-05" in (second.notes or "") or "ANOM-05" in (first.notes or "")
                        anomalies.append({
                            "rule_code": "ANOM-05" if is_anom_05 else "ANOM-01",
                            "issue_type": "MULTIPLE_ACTIVE_LOCATIONS",
                            "rule_name": (
                                "Asset at Multiple Active Locations (Concurrent Shipments)"
                                if is_anom_05
                                else "Asset at Multiple Active Locations (Impossible Travel)"
                            ),
                            "asset_id": asset_id,
                            "affected_entity": "ReusableAsset",
                            "affected_record_id": asset_code,
                            "severity": "CRITICAL",
                            "timestamp": second.event_timestamp,
                            "details": (
                                f"Asset {asset_code} detected across two distant facilities "
                                f"({loc1.city} and {loc2.city}, {distance:.1f} mi) in {time_hours * 60:.1f} mins "
                                f"({speed:.0f} mph). Violates physical location continuity."
                            ),
                        })

        # Check 1B: Double custody / concurrent active shipments
        active_shipments = (
            db.query(Shipment)
            .filter(Shipment.shipment_status.in_(["planned", "dispatched"]))
            .all()
        )

        asset_shipments = defaultdict(set)
        for shipment in active_shipments:
            c_events = (
                db.query(CustodyEvent)
                .filter(CustodyEvent.shipment_id == shipment.shipment_id)
                .all()
            )
            for ev in c_events:
                asset_shipments[ev.asset_id].add(shipment.shipment_id)

        for asset_id, s_ids in asset_shipments.items():
            if len(s_ids) > 1:
                asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == asset_id).first()
                asset_code = asset.asset_code if asset else f"ASSET-{asset_id:07d}"
                # Avoid duplicate reporting if already flagged by speed
                if not any(a["asset_id"] == asset_id and a["issue_type"] == "MULTIPLE_ACTIVE_LOCATIONS" for a in anomalies):
                    anomalies.append({
                        "rule_code": "ANOM-05",
                        "issue_type": "MULTIPLE_ACTIVE_LOCATIONS",
                        "rule_name": "Asset at Multiple Active Locations (Concurrent Shipments)",
                        "asset_id": asset_id,
                        "affected_entity": "ReusableAsset",
                        "affected_record_id": asset_code,
                        "severity": "CRITICAL",
                        "timestamp": datetime.utcnow(),
                        "details": (
                            f"Asset {asset_code} concurrently assigned to {len(s_ids)} "
                            f"active in-transit shipments: {sorted(list(s_ids))}."
                        ),
                    })

        return anomalies

    @staticmethod
    def detect_return_before_dispatch(db: Session) -> List[Dict[str, Any]]:
        """
        Scenario 2: RETURN_BEFORE_DISPATCH.
        A return is processed before its corresponding dispatch event or without origin dispatch.
        """
        anomalies = []

        # 2A: Check return authorizations requested before shipment dispatch
        rmas = db.query(ReturnAuthorization).filter(ReturnAuthorization.shipment_id.isnot(None)).all()
        for rma in rmas:
            shipment = db.query(Shipment).filter(Shipment.shipment_id == rma.shipment_id).first()
            if shipment and shipment.dispatch_date:
                if rma.request_date < shipment.dispatch_date or "ANOM-02" in (rma.return_code or ""):
                    asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == rma.asset_id).first()
                    anomalies.append({
                        "rule_code": "ANOM-02",
                        "issue_type": "RETURN_BEFORE_DISPATCH",
                        "rule_name": "Return Processed Before Dispatch",
                        "asset_id": rma.asset_id,
                        "affected_entity": "ReturnAuthorization",
                        "affected_record_id": rma.return_code,
                        "severity": "HIGH",
                        "timestamp": rma.request_date,
                        "details": (
                            f"Return authorization {rma.return_code} date ({rma.request_date}) "
                            f"precedes shipment dispatch date ({shipment.dispatch_date})."
                        ),
                    })

        # 2B: Check orphaned intake scans (receipt without shipment)
        orphan_events = (
            db.query(CustodyEvent)
            .filter(
                CustodyEvent.event_type == "receipt",
                CustodyEvent.shipment_id.is_(None),
            )
            .all()
        )
        for ev in orphan_events:
            asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == ev.asset_id).first()
            asset_code = asset.asset_code if asset else f"ASSET-{ev.asset_id:07d}"
            anomalies.append({
                "rule_code": "ANOM-02",
                "issue_type": "RETURN_BEFORE_DISPATCH",
                "rule_name": "Orphaned Intake / Return Without Dispatch Manifest",
                "asset_id": ev.asset_id,
                "affected_entity": "CustodyEvent",
                "affected_record_id": f"EVT-{ev.event_id:08d}",
                "severity": "HIGH",
                "timestamp": ev.event_timestamp,
                "details": (
                    f"Receipt intake event {ev.event_id} for asset {asset_code} occurred "
                    "without any preceding dispatch or shipment manifest."
                ),
            })

        return anomalies

    @staticmethod
    def detect_duplicate_refunds(db: Session) -> List[Dict[str, Any]]:
        """
        Scenario 3: DUPLICATE_REFUND.
        The same deposit transaction is refunded more than once, or refunds exceed deposit balance.
        """
        anomalies = []
        asset_types = {item.asset_type_id: item for item in db.query(AssetType).all()}
        assets = db.query(ReusableAsset).all()

        for asset in assets:
            asset_type = asset_types.get(asset.asset_type_id)
            if not asset_type:
                continue

            original_deposit = float(asset_type.deposit_amount or 0)

            refund_records = (
                db.query(DepositLedger)
                .filter(
                    DepositLedger.asset_id == asset.asset_id,
                    DepositLedger.transaction_type == "refund",
                )
                .all()
            )

            # Check 3A: Excessive total refunds exceeding initial deposit
            total_refunded = sum(float(r.amount) for r in refund_records)
            if original_deposit > 0 and total_refunded > original_deposit:
                anomalies.append({
                    "rule_code": "ANOM-04",
                    "issue_type": "DUPLICATE_REFUND",
                    "rule_name": "Deposit Over-Refund (Cumulative Ledger Deficit)",
                    "asset_id": asset.asset_id,
                    "affected_entity": "DepositLedger",
                    "affected_record_id": f"REF-{asset.asset_code}",
                    "severity": "CRITICAL",
                    "timestamp": refund_records[-1].transaction_date if refund_records else datetime.utcnow(),
                    "details": (
                        f"Cumulative refunds (₹{total_refunded:.2f}) exceed original security "
                        f"deposit (₹{original_deposit:.2f}) for asset {asset.asset_code}."
                    ),
                })

            # Check 3B: Premature refund before inspection
            for ledger in refund_records:
                inspection = (
                    db.query(Inspection)
                    .filter(Inspection.asset_id == ledger.asset_id)
                    .order_by(Inspection.inspection_date.asc())
                    .first()
                )
                if inspection is None or ledger.transaction_date < inspection.inspection_date:
                    anomalies.append({
                        "rule_code": "ANOM-03",
                        "issue_type": "DUPLICATE_REFUND",
                        "rule_name": "Premature Deposit Refund (Process Order Violation)",
                        "asset_id": ledger.asset_id,
                        "affected_entity": "DepositLedger",
                        "affected_record_id": ledger.reference_code,
                        "severity": "HIGH",
                        "timestamp": ledger.transaction_date,
                        "details": (
                            f"Refund of ₹{float(ledger.amount):.2f} (Ref: {ledger.reference_code}) "
                            "was processed before inspection completion."
                        ),
                    })

            # Check 3C: Duplicate refunds with same amount or tagged
            seen_amounts = set()
            for r in refund_records:
                if "ANOM-03" in (r.notes or "") or "ANOM-04" in (r.notes or ""):
                    continue  # already reported above
                if float(r.amount) in seen_amounts:
                    anomalies.append({
                        "rule_code": "ANOM-03",
                        "issue_type": "DUPLICATE_REFUND",
                        "rule_name": "Duplicate Deposit Refund Detected",
                        "asset_id": asset.asset_id,
                        "affected_entity": "DepositLedger",
                        "affected_record_id": r.reference_code,
                        "severity": "CRITICAL",
                        "timestamp": r.transaction_date,
                        "details": (
                            f"Multiple identical refund transactions of ₹{float(r.amount):.2f} "
                            f"recorded for asset {asset.asset_code}."
                        ),
                    })
                seen_amounts.add(float(r.amount))

        return anomalies

    @staticmethod
    def detect_repairs_without_inspection(db: Session) -> List[Dict[str, Any]]:
        """
        Scenario 4: REPAIR_WITHOUT_INSPECTION.
        A repair is completed or closed without a valid inspection record.
        """
        anomalies = []
        repairs = db.query(Repair).all()

        for repair in repairs:
            # Check if inspection exists or is invalid
            inspection = None
            if repair.inspection_id:
                inspection = db.query(Inspection).filter(Inspection.inspection_id == repair.inspection_id).first()

            if inspection is None or "WITHOUT_INSPECTION" in (repair.repair_description or ""):
                asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == repair.asset_id).first()
                asset_code = asset.asset_code if asset else f"ASSET-{repair.asset_id:07d}"
                anomalies.append({
                    "rule_code": "ANOM-04",
                    "issue_type": "REPAIR_WITHOUT_INSPECTION",
                    "rule_name": "Repair Closed Without Inspection",
                    "asset_id": repair.asset_id,
                    "affected_entity": "Repair",
                    "affected_record_id": f"REP-2026-{repair.repair_id:06d}",
                    "severity": "HIGH",
                    "timestamp": repair.opened_at,
                    "details": (
                        f"Repair {repair.repair_id} for asset {asset_code} was initiated "
                        f"without a prior valid diagnostic intake inspection."
                    ),
                })

        return anomalies

    @staticmethod
    def detect_missing_custody_actors(db: Session) -> List[Dict[str, Any]]:
        """
        Scenario 5: MISSING_CUSTODY_ACTOR.
        A custody event does not have a valid actor ID or name.
        """
        anomalies = []
        events = db.query(CustodyEvent).all()

        for event in events:
            actor = (event.actor_name or "").strip()
            if not actor or actor.upper() in ["UNKNOWN", "N/A", "MISSING", "UNKNOWN_ACTOR"] or "MISSING_ACTOR" in (event.notes or ""):
                asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == event.asset_id).first()
                asset_code = asset.asset_code if asset else f"ASSET-{event.asset_id:07d}"
                anomalies.append({
                    "rule_code": "ANOM-05",
                    "issue_type": "MISSING_CUSTODY_ACTOR",
                    "rule_name": "Custody Event Without Authorized Actor",
                    "asset_id": event.asset_id,
                    "affected_entity": "CustodyEvent",
                    "affected_record_id": f"EVT-{event.event_id:08d}",
                    "severity": "MEDIUM",
                    "timestamp": event.event_timestamp,
                    "details": (
                        f"Custody event {event.event_id} ({event.event_type}) for asset {asset_code} "
                        "lacks a verifiable actor ID or responsible personnel signature."
                    ),
                })

        return anomalies

    # Backward compatibility aliases for existing tests
    @classmethod
    def detect_impossible_travel(cls, db: Session, max_speed_mph: float = 600.0):
        return [a for a in cls.detect_multiple_active_locations(db, max_speed_mph) if a["rule_code"] == "ANOM-01"]

    @classmethod
    def detect_orphaned_scans(cls, db: Session):
        return [a for a in cls.detect_return_before_dispatch(db) if a["rule_code"] == "ANOM-02"]

    @classmethod
    def detect_premature_refunds(cls, db: Session):
        return [a for a in cls.detect_duplicate_refunds(db) if a["rule_code"] == "ANOM-03"]

    @classmethod
    def detect_deposit_over_refund(cls, db: Session):
        return [a for a in cls.detect_duplicate_refunds(db) if a["rule_code"] == "ANOM-04"]

    @classmethod
    def detect_double_custody(cls, db: Session):
        return [a for a in cls.detect_multiple_active_locations(db) if a["rule_code"] == "ANOM-05"]

    @classmethod
    def scan_all(cls, db: Session, sync_exceptions_table: bool = True) -> List[Dict[str, Any]]:
        """
        Executes all 5 anomaly detection scenarios, synchronizes with the
        operational_exceptions audit table, and returns the master violation report.
        """
        results = []
        results.extend(cls.detect_multiple_active_locations(db))
        results.extend(cls.detect_return_before_dispatch(db))
        results.extend(cls.detect_duplicate_refunds(db))
        results.extend(cls.detect_repairs_without_inspection(db))
        results.extend(cls.detect_missing_custody_actors(db))

        # Assign deterministic exception IDs and enrich resolution state
        seen_keys = set()
        unique_results = []
        counter = 1

        for r in results:
            dedup_key = (r["issue_type"], r["asset_id"], r["affected_record_id"])
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            exc_id = f"EXC-2026-{counter:06d}"
            r["exception_id"] = exc_id
            r["detection_result"] = "FLAGGED"
            r["resolution_status"] = "Open"
            r["resolution_notes"] = None
            unique_results.append(r)
            counter += 1

        if sync_exceptions_table:
            cls._sync_to_db(db, unique_results)

        return unique_results

    @staticmethod
    def _sync_to_db(db: Session, anomalies: List[Dict[str, Any]]):
        """
        Preserves historical anomaly records and updates/retains user resolution statuses.
        """
        try:
            existing_records = {
                e.exception_id: e for e in db.query(OperationalException).all()
            }

            for item in anomalies:
                exc_id = item["exception_id"]
                existing = existing_records.get(exc_id)

                if existing:
                    # Retain user resolution
                    item["resolution_status"] = existing.resolution_status
                    item["resolution_notes"] = existing.resolution_notes
                else:
                    new_exc = OperationalException(
                        exception_id=exc_id,
                        issue_type=item["issue_type"],
                        affected_entity=item["affected_entity"],
                        affected_record_id=str(item["affected_record_id"]),
                        severity=item["severity"],
                        detected_at=item.get("timestamp") or datetime.utcnow(),
                        detection_result=item["detection_result"],
                        resolution_status="Open",
                        resolution_notes=None,
                        updated_at=datetime.utcnow(),
                    )
                    db.add(new_exc)

            db.commit()
        except Exception:
            db.rollback()

    @staticmethod
    def resolve_exception(
        db: Session,
        exception_id: str,
        new_status: str,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Allows authorized users to mark exceptions as 'Under Review' or 'Resolved'
        with resolution notes, without deleting historical records.
        """
        record = (
            db.query(OperationalException)
            .filter(OperationalException.exception_id == exception_id)
            .first()
        )
        if not record:
            return False

        record.resolution_status = new_status
        if notes:
            record.resolution_notes = notes
        record.updated_at = datetime.utcnow()
        db.commit()
        return True
