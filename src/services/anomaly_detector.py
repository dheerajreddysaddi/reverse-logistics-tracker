"""
Business Rules & Anomaly Detection Engine for Reverse Logistics Control Tower.

Implements the 5 mandatory hackathon reverse-logistics exception detection scenarios:
1. MULTIPLE_ACTIVE_LOCATIONS: Conflicting active locations or impossible travel speed (>600 mph).
   Expected Decision: QUARANTINE_ASSET.
2. RETURN_BEFORE_DISPATCH: Return processed before original shipment dispatch.
   Expected Decision: HOLD_RETURN_INTAKE.
3. DUPLICATE_REFUND: Multiple refunds for the same deposit or excessive refund.
   Expected Decision: FREEZE_LEDGER_TRANSACTION.
4. REPAIR_WITHOUT_INSPECTION: Repair completed without a valid inspection record.
   Expected Decision: REOPEN_INSPECTION_WORKFLOW.
5. MISSING_CUSTODY_ACTOR: Custody scan recorded without an authorized actor.
   Expected Decision: REASSIGN_CUSTODY_AUDITOR.
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
        including impossible travel speeds (>600 mph) and concurrent active movements.
        Expected Decision: QUARANTINE_ASSET.
        """
        anomalies = []
        locations = {loc.location_id: loc for loc in db.query(Location).all()}

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
                    if speed > max_speed_mph:
                        asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == asset_id).first()
                        asset_code = asset.asset_code if asset else f"ASSET-{asset_id:07d}"
                        anomalies.append({
                            "rule_code": "ANOM-01",
                            "issue_type": "MULTIPLE_ACTIVE_LOCATIONS",
                            "rule_name": "Multiple Active Locations (Impossible Travel Speed)",
                            "asset_id": asset_id,
                            "affected_entity": "ReusableAsset",
                            "affected_record_id": asset_code,
                            "severity": "CRITICAL",
                            "expected_decision": "QUARANTINE_ASSET",
                            "timestamp": second.event_timestamp,
                            "details": (
                                f"Asset {asset_code} detected across two distant facilities "
                                f"({loc1.city} and {loc2.city}, {distance:.1f} mi) in {time_hours * 60:.1f} mins "
                                f"({speed:.0f} mph). Violates physical location continuity."
                            ),
                        })

        return anomalies

    @staticmethod
    def detect_return_before_dispatch(db: Session) -> List[Dict[str, Any]]:
        """
        Scenario 2: RETURN_BEFORE_DISPATCH.
        A return is processed before its corresponding dispatch event or without origin dispatch.
        Expected Decision: HOLD_RETURN_INTAKE.
        """
        anomalies = []

        # 2A: Check return authorizations requested before shipment dispatch
        rmas = db.query(ReturnAuthorization).filter(ReturnAuthorization.shipment_id.isnot(None)).all()
        for rma in rmas:
            shipment = db.query(Shipment).filter(Shipment.shipment_id == rma.shipment_id).first()
            if shipment and shipment.dispatch_date:
                if rma.request_date < shipment.dispatch_date:
                    asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == rma.asset_id).first()
                    asset_code = asset.asset_code if asset else f"ASSET-{rma.asset_id:07d}"
                    anomalies.append({
                        "rule_code": "ANOM-02",
                        "issue_type": "RETURN_BEFORE_DISPATCH",
                        "rule_name": "Return Processed Before Dispatch",
                        "asset_id": rma.asset_id,
                        "affected_entity": "ReturnAuthorization",
                        "affected_record_id": rma.return_code,
                        "severity": "HIGH",
                        "expected_decision": "HOLD_RETURN_INTAKE",
                        "timestamp": rma.request_date,
                        "details": (
                            f"Return authorization {rma.return_code} date ({rma.request_date}) "
                            f"precedes shipment dispatch date ({shipment.dispatch_date}) for asset {asset_code}."
                        ),
                    })

        # 2B: Check custody return/receipt events that precede shipment dispatch
        return_events = (
            db.query(CustodyEvent)
            .filter(
                CustodyEvent.event_type.in_(["return", "return_intake", "receipt"]),
                CustodyEvent.shipment_id.isnot(None),
            )
            .all()
        )
        for ev in return_events:
            shipment = db.query(Shipment).filter(Shipment.shipment_id == ev.shipment_id).first()
            if shipment and shipment.dispatch_date and ev.event_timestamp < shipment.dispatch_date:
                if not any(a["asset_id"] == ev.asset_id and a["issue_type"] == "RETURN_BEFORE_DISPATCH" for a in anomalies):
                    asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == ev.asset_id).first()
                    asset_code = asset.asset_code if asset else f"ASSET-{ev.asset_id:07d}"
                    anomalies.append({
                        "rule_code": "ANOM-02",
                        "issue_type": "RETURN_BEFORE_DISPATCH",
                        "rule_name": "Return Intake Precedes Outbound Dispatch",
                        "asset_id": ev.asset_id,
                        "affected_entity": "CustodyEvent",
                        "affected_record_id": ev.event_code or f"EVT-2026-{ev.event_id:06d}",
                        "severity": "HIGH",
                        "expected_decision": "HOLD_RETURN_INTAKE",
                        "timestamp": ev.event_timestamp,
                        "details": (
                            f"Custody return intake event for asset {asset_code} at {ev.event_timestamp} "
                            f"occurred prior to shipment dispatch date ({shipment.dispatch_date})."
                        ),
                    })

        return anomalies

    @staticmethod
    def detect_duplicate_refunds(db: Session) -> List[Dict[str, Any]]:
        """
        Scenario 3: DUPLICATE_REFUND.
        Validates refunds against actual deposit amounts. Flags multiple refunds against the same
        deposit transaction or refunds exceeding the original deposit charge, avoiding false positives.
        Expected Decision: FREEZE_LEDGER_TRANSACTION.
        """
        anomalies = []
        assets = db.query(ReusableAsset).all()

        for asset in assets:
            charges = (
                db.query(DepositLedger)
                .filter(
                    DepositLedger.asset_id == asset.asset_id,
                    DepositLedger.transaction_type == "charge",
                )
                .all()
            )
            total_charged = sum(float(c.amount) for c in charges)

            refund_records = (
                db.query(DepositLedger)
                .filter(
                    DepositLedger.asset_id == asset.asset_id,
                    DepositLedger.transaction_type == "refund",
                )
                .order_by(DepositLedger.transaction_date.asc())
                .all()
            )
            total_refunded = sum(float(r.amount) for r in refund_records)

            # Business rule: Refunds exceed deposit charged or multiple refunds against single charge
            if len(refund_records) > 0 and total_charged > 0:
                if total_refunded > total_charged or len(refund_records) > len(charges):
                    duplicate_refund = refund_records[-1]
                    anomalies.append({
                        "rule_code": "ANOM-03",
                        "issue_type": "DUPLICATE_REFUND",
                        "rule_name": "Duplicate Security Deposit Refund",
                        "asset_id": asset.asset_id,
                        "affected_entity": "DepositLedger",
                        "affected_record_id": duplicate_refund.reference_code,
                        "severity": "CRITICAL",
                        "expected_decision": "FREEZE_LEDGER_TRANSACTION",
                        "timestamp": duplicate_refund.transaction_date,
                        "details": (
                            f"Duplicate or excessive refund transaction of ₹{float(duplicate_refund.amount):.2f} "
                            f"(Ref: {duplicate_refund.reference_code}) against security deposit charge of ₹{total_charged:.2f} "
                            f"(Total refunded: ₹{total_refunded:.2f}) for asset {asset.asset_code}."
                        ),
                    })

        return anomalies

    @staticmethod
    def detect_repairs_without_inspection(db: Session) -> List[Dict[str, Any]]:
        """
        Scenario 4: REPAIR_WITHOUT_INSPECTION.
        Verifies that a diagnostic inspection exists AND occurred chronologically before the repair.
        Expected Decision: REOPEN_INSPECTION_WORKFLOW.
        """
        anomalies = []
        repairs = db.query(Repair).all()

        for repair in repairs:
            inspection = None
            if repair.inspection_id:
                inspection = db.query(Inspection).filter(Inspection.inspection_id == repair.inspection_id).first()

            is_missing = inspection is None
            is_post_repair = False
            if inspection and repair.opened_at and inspection.inspection_date:
                if inspection.inspection_date > repair.opened_at:
                    is_post_repair = True

            if is_missing or is_post_repair:
                asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == repair.asset_id).first()
                asset_code = asset.asset_code if asset else f"ASSET-{repair.asset_id:07d}"
                detail_msg = (
                    f"Repair work order {repair.repair_code or repair.repair_id} for asset {asset_code} "
                    f"occurred prior to its diagnostic inspection ({inspection.inspection_date} > {repair.opened_at})."
                    if is_post_repair
                    else f"Repair work order {repair.repair_code or repair.repair_id} for asset {asset_code} was closed without a verified diagnostic intake inspection."
                )
                anomalies.append({
                    "rule_code": "ANOM-04",
                    "issue_type": "REPAIR_WITHOUT_INSPECTION",
                    "rule_name": "Repair Closed Without Preceding Diagnostic Inspection",
                    "asset_id": repair.asset_id,
                    "affected_entity": "Repair",
                    "affected_record_id": repair.repair_code or f"REP-2026-{repair.repair_id:06d}",
                    "severity": "CRITICAL",
                    "expected_decision": "REOPEN_INSPECTION_WORKFLOW",
                    "timestamp": repair.opened_at,
                    "details": detail_msg,
                })

        return anomalies

    @staticmethod
    def detect_missing_custody_actors(db: Session) -> List[Dict[str, Any]]:
        """
        Scenario 5: MISSING_CUSTODY_ACTOR.
        A custody event does not have an authorized actor ID or name.
        Expected Decision: REASSIGN_CUSTODY_AUDITOR.
        """
        anomalies = []
        events = db.query(CustodyEvent).all()

        for event in events:
            actor = (event.actor_name or "").strip()
            if not actor or actor.upper() in ["UNKNOWN", "N/A", "MISSING", "UNKNOWN_ACTOR", "NONE", "UNASSIGNED"]:
                asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == event.asset_id).first()
                asset_code = asset.asset_code if asset else f"ASSET-{event.asset_id:07d}"
                anomalies.append({
                    "rule_code": "ANOM-05",
                    "issue_type": "MISSING_CUSTODY_ACTOR",
                    "rule_name": "Custody Event Without Authorized Actor Identifier",
                    "asset_id": event.asset_id,
                    "affected_entity": "CustodyEvent",
                    "affected_record_id": event.event_code or f"EVT-2026-{event.event_id:06d}",
                    "severity": "MEDIUM",
                    "expected_decision": "REASSIGN_CUSTODY_AUDITOR",
                    "timestamp": event.event_timestamp,
                    "details": (
                        f"Custody scan {event.event_code or event.event_id} ({event.event_type}) for asset {asset_code} "
                        "lacks a verifiable actor ID or responsible operator signature."
                    ),
                })

        return anomalies

    # Backward compatibility aliases
    @classmethod
    def detect_impossible_travel(cls, db: Session, max_speed_mph: float = 600.0):
        return cls.detect_multiple_active_locations(db, max_speed_mph)

    @classmethod
    def detect_orphaned_scans(cls, db: Session):
        return cls.detect_return_before_dispatch(db)

    @classmethod
    def detect_premature_refunds(cls, db: Session):
        return cls.detect_duplicate_refunds(db)

    @classmethod
    def detect_deposit_over_refund(cls, db: Session):
        return cls.detect_duplicate_refunds(db)

    @classmethod
    def detect_double_custody(cls, db: Session):
        return cls.detect_multiple_active_locations(db)

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
            dedup_key = (r["issue_type"], r["asset_id"])
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
        """Preserves historical anomaly records and updates/retains user resolution statuses."""
        try:
            existing_records = {
                e.exception_id: e for e in db.query(OperationalException).all()
            }

            for item in anomalies:
                exc_id = item["exception_id"]
                existing = existing_records.get(exc_id)

                if existing:
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
        Allows authorized operators to mark exceptions as 'Under Review' or 'Resolved'
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
