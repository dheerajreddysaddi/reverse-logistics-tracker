
"""
Stage 7: Ground Truth Registry.

Builds an authoritative benchmark using the Stage 6
anomaly markers stored in CustodyEvent and DepositLedger.
"""

import json
import os
from typing import Dict, Any

from sqlalchemy.orm import Session

from src.database.models import (
    ReusableAsset,
    CustodyEvent,
    DepositLedger,
)

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

GROUND_TRUTH_PATH = os.path.join(
    BASE_DIR,
    "data",
    "processed",
    "ground_truth.json",
)

RULE_CODES = [
    "ANOM-01",
    "ANOM-02",
    "ANOM-03",
    "ANOM-04",
    "ANOM-05",
]


def build_and_save_ground_truth(db: Session) -> Dict[str, Any]:
    """
    Labels every asset as CLEAN or ANOMALOUS.

    Stage 6 markers are used as the authoritative source
    for the intentionally injected test anomalies.
    """

    injected_map = {}

    # Anomalies recorded in custody events:
    # ANOM-01, ANOM-02 and ANOM-05.
    custody_events = (
        db.query(CustodyEvent)
        .filter(CustodyEvent.notes.like("STAGE6:%"))
        .all()
    )

    for event in custody_events:
        notes = event.notes or ""

        for rule_code in RULE_CODES:
            if f"STAGE6:{rule_code}" in notes:
                injected_map.setdefault(
                    event.asset_id, set()
                ).add(rule_code)

    # Anomalies recorded in deposit ledger:
    # ANOM-03 and ANOM-04.
    ledger_entries = (
        db.query(DepositLedger)
        .filter(DepositLedger.notes.like("STAGE6:%"))
        .all()
    )

    for entry in ledger_entries:
        notes = entry.notes or ""

        for rule_code in RULE_CODES:
            if f"STAGE6:{rule_code}" in notes:
                injected_map.setdefault(
                    entry.asset_id, set()
                ).add(rule_code)

    ground_truth = {}

    assets = db.query(ReusableAsset).order_by(
        ReusableAsset.asset_id
    ).all()

    for asset in assets:

        expected_rules = sorted(
            injected_map.get(asset.asset_id, set())
        )

        is_anomaly = len(expected_rules) > 0

        ground_truth[str(asset.asset_id)] = {
            "asset_id": asset.asset_id,
            "asset_code": asset.asset_code,
            "label": "ANOMALOUS" if is_anomaly else "CLEAN",
            "is_anomaly": is_anomaly,
            "expected_rules": expected_rules,
        }

    os.makedirs(
        os.path.dirname(GROUND_TRUTH_PATH),
        exist_ok=True,
    )

    with open(
        GROUND_TRUTH_PATH,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(ground_truth, file, indent=2)

    print(
        f"Ground truth generated for {len(ground_truth)} assets."
    )

    return ground_truth


def load_ground_truth() -> Dict[str, Any]:
    """Load the saved ground-truth JSON file."""

    if not os.path.exists(GROUND_TRUTH_PATH):
        raise FileNotFoundError(
            "Ground truth not found. Run the evaluation builder first."
        )

    with open(
        GROUND_TRUTH_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)
