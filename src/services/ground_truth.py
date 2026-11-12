"""
ReLoop 360 Ground Truth Registry.

Maintains an authoritative benchmark distinguishing clean operations from
intentionally injected synthetic anomalies for empirical model evaluation.

Generates both:
- data/processed/ground_truth.json
- data/processed/ground_truth.csv

With exact required schema:
[anomaly_id, affected_entity, affected_record_id, issue_type, expected_detection, expected_decision, severity]
"""

import csv
import json
import os
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from src.database.models import (
    ReusableAsset,
    CustodyEvent,
    DepositLedger,
    ReturnAuthorization,
    Repair,
)

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

GROUND_TRUTH_JSON_PATH = os.path.join(
    BASE_DIR, "data", "processed", "ground_truth.json"
)
GROUND_TRUTH_CSV_PATH = os.path.join(
    BASE_DIR, "data", "processed", "ground_truth.csv"
)

# Rule to Issue Type & Decision mapping
RULE_METADATA = {
    "ANOM-01": {
        "issue_type": "MULTIPLE_ACTIVE_LOCATIONS",
        "affected_entity": "ReusableAsset",
        "expected_decision": "QUARANTINE_ASSET",
        "severity": "CRITICAL",
    },
    "ANOM-02": {
        "issue_type": "RETURN_BEFORE_DISPATCH",
        "affected_entity": "CustodyEvent",
        "expected_decision": "HOLD_RETURN_INTAKE",
        "severity": "HIGH",
    },
    "ANOM-03": {
        "issue_type": "DUPLICATE_REFUND",
        "affected_entity": "DepositLedger",
        "expected_decision": "FREEZE_LEDGER_TRANSACTION",
        "severity": "HIGH",
    },
    "ANOM-04": {
        "issue_type": "REPAIR_WITHOUT_INSPECTION",
        "affected_entity": "Repair",
        "expected_decision": "REOPEN_INSPECTION_WORKFLOW",
        "severity": "CRITICAL",
    },
    "ANOM-05": {
        "issue_type": "MISSING_CUSTODY_ACTOR",
        "affected_entity": "CustodyEvent",
        "expected_decision": "REASSIGN_CUSTODY_AUDITOR",
        "severity": "MEDIUM",
    },
}

RULE_CODES = list(RULE_METADATA.keys())


def build_and_save_ground_truth(db: Session) -> Dict[str, Any]:
    """
    Labels every asset as CLEAN or ANOMALOUS, and exports the ground truth
    to both JSON and CSV files.
    """
    injected_map: Dict[int, set] = {}

    # 1. Custody event anomalies
    events = (
        db.query(CustodyEvent)
        .filter(CustodyEvent.notes.like("STAGE6:%"))
        .all()
    )
    for event in events:
        notes = event.notes or ""
        for rule_code in RULE_CODES:
            if f"STAGE6:{rule_code}" in notes:
                injected_map.setdefault(event.asset_id, set()).add(rule_code)

    # 2. Deposit ledger anomalies
    entries = (
        db.query(DepositLedger)
        .filter(DepositLedger.notes.like("STAGE6:%"))
        .all()
    )
    for entry in entries:
        notes = entry.notes or ""
        for rule_code in RULE_CODES:
            if f"STAGE6:{rule_code}" in notes:
                injected_map.setdefault(entry.asset_id, set()).add(rule_code)

    ground_truth_asset_map = {}
    ground_truth_records: List[Dict[str, Any]] = []

    assets = db.query(ReusableAsset).order_by(ReusableAsset.asset_id).all()
    anomaly_counter = 1

    for asset in assets:
        expected_rules = sorted(list(injected_map.get(asset.asset_id, set())))
        is_anomaly = len(expected_rules) > 0

        issue_types = [RULE_METADATA[r]["issue_type"] for r in expected_rules if r in RULE_METADATA]

        ground_truth_asset_map[str(asset.asset_id)] = {
            "asset_id": asset.asset_id,
            "asset_code": asset.asset_code,
            "label": "ANOMALOUS" if is_anomaly else "CLEAN",
            "is_anomaly": is_anomaly,
            "expected_rules": expected_rules,
            "issue_types": issue_types,
        }

        # Add to ground truth tabular records
        for r_code in expected_rules:
            meta = RULE_METADATA.get(r_code, {
                "issue_type": "ANOMALY",
                "affected_entity": "ReusableAsset",
                "expected_decision": "INVESTIGATE",
                "severity": "HIGH",
            })
            record = {
                "anomaly_id": f"GT-ANOM-2026-{anomaly_counter:04d}",
                "affected_entity": meta["affected_entity"],
                "affected_record_id": asset.asset_code,
                "issue_type": meta["issue_type"],
                "expected_detection": "FLAGGED",
                "expected_decision": meta["expected_decision"],
                "severity": meta["severity"],
            }
            ground_truth_records.append(record)
            anomaly_counter += 1

    os.makedirs(os.path.dirname(GROUND_TRUTH_JSON_PATH), exist_ok=True)

    # Save JSON
    with open(GROUND_TRUTH_JSON_PATH, "w", encoding="utf-8") as file:
        json.dump(ground_truth_asset_map, file, indent=2)

    # Save CSV
    if ground_truth_records:
        fieldnames = [
            "anomaly_id",
            "affected_entity",
            "affected_record_id",
            "issue_type",
            "expected_detection",
            "expected_decision",
            "severity",
        ]
        with open(GROUND_TRUTH_CSV_PATH, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(ground_truth_records)

    print(f"Ground truth generated: {len(ground_truth_records)} anomalies across {len(ground_truth_asset_map)} assets.")
    return ground_truth_asset_map


def load_ground_truth() -> Dict[str, Any]:
    """Load the saved ground-truth JSON file."""
    if not os.path.exists(GROUND_TRUTH_JSON_PATH):
        raise FileNotFoundError("Ground truth not found. Run builder first.")
    with open(GROUND_TRUTH_JSON_PATH, "r", encoding="utf-8") as file:
        return json.load(file)
