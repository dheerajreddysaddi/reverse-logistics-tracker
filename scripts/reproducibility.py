"""
Reproducibility Verification Engine for Reverse Logistics Control Tower.

Executes two independent generation runs in isolated temporary databases
using the fixed project seed (20261022), exports canonicalized data,
computes SHA-256 checksums, and outputs data/processed/reproducibility_report.json.
"""

import hashlib
import json
import os
import shutil
import tempfile
from typing import Dict, Any, List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.connection import Base
from src.database.models import (
    Owner,
    Location,
    AssetType,
    ReusableAsset,
    Shipment,
    CustodyEvent,
    ReturnAuthorization,
    Inspection,
    Repair,
    DepositLedger,
    OperationalException,
)
from src.database.seed_master import (
    seed_owners,
    seed_locations,
    seed_asset_types,
)
from src.generator.asset_generator import generate_assets_batch
from src.generator.custody_generator import (
    generate_shipments_and_events_batch,
    bulk_insert_shipments_and_events,
)
from src.generator.rma_generator import (
    generate_reverse_logistics_batch,
    bulk_insert_reverse_logistics,
)
from src.generator.anomaly_injector import inject_mandatory_edge_cases
from src.services.anomaly_detector import AnomalyDetector
from src.services.ground_truth import build_and_save_ground_truth

PROJECT_SEED = 20261022
REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "processed",
    "reproducibility_report.json",
)

TABLE_MODELS = [
    ("owners", Owner, "owner_id"),
    ("locations", Location, "location_id"),
    ("asset_types", AssetType, "asset_type_id"),
    ("reusable_assets", ReusableAsset, "asset_id"),
    ("shipments", Shipment, "shipment_id"),
    ("custody_events", CustodyEvent, "event_id"),
    ("return_authorizations", ReturnAuthorization, "return_id"),
    ("inspections", Inspection, "inspection_id"),
    ("repairs", Repair, "repair_id"),
    ("deposit_ledger", DepositLedger, "ledger_id"),
    ("operational_exceptions", OperationalException, "exception_id"),
]


def run_pipeline_in_db(db_path: str, seed: int = PROJECT_SEED, scale: str = "starter") -> Dict[str, Any]:
    """Runs the full generation and anomaly detection pipeline on an isolated database."""
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # 1. Master data
        seed_owners(db)
        seed_locations(db)
        seed_asset_types(db)
        db.commit()

        # 2. Assets
        asset_count = 500 if scale == "starter" else 20000
        records = generate_assets_batch(db, count=asset_count, seed=seed)
        db.bulk_insert_mappings(ReusableAsset, records)
        db.commit()

        # 3. Shipments & Custody
        shipment_count = 250 if scale == "starter" else 10000
        shipment_recs, custody_recs = generate_shipments_and_events_batch(
            db, shipment_count=shipment_count, seed=seed
        )
        bulk_insert_shipments_and_events(db, shipment_recs, custody_recs)

        # 4. Reverse Logistics
        rma_count = 100 if scale == "starter" else 4000
        rmas, inspections, repairs, ledgers = generate_reverse_logistics_batch(
            db, return_count=rma_count, seed=seed
        )
        bulk_insert_reverse_logistics(db, rmas, inspections, repairs, ledgers)

        # 5. Injected Anomalies
        inject_mandatory_edge_cases(db)

        # 6. Detection & Exceptions
        AnomalyDetector.scan_all(db, sync_exceptions_table=True)

        # Export canonical data & calculate counts and hashes
        counts = {}
        hashes = {}

        for table_name, model, pk_col in TABLE_MODELS:
            rows = db.query(model).order_by(getattr(model, pk_col)).all()
            counts[table_name] = len(rows)

            # Canonical representation for checksum
            canonical_records = []
            for row in rows:
                row_dict = {}
                for c in model.__table__.columns:
                    # Ignore non-deterministic system clock timestamps
                    if table_name == "operational_exceptions" and c.name in ("updated_at", "detected_at"):
                        continue
                    row_dict[c.name] = str(getattr(row, c.name))
                canonical_records.append(row_dict)

            serialized = json.dumps(canonical_records, sort_keys=True, separators=(',', ':'))
            h = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
            hashes[table_name] = h

        return {"counts": counts, "hashes": hashes}

    finally:
        db.close()
        engine.dispose()


def verify_reproducibility(seed: int = PROJECT_SEED, scale: str = "starter") -> Dict[str, Any]:
    """Generates two independent databases and produces a formal reproducibility report."""
    print("=" * 60)
    print(" REPRODUCIBILITY VERIFICATION PIPELINE")
    print(f" Seed:  {seed}")
    print(f" Scale: {scale}")
    print("=" * 60)

    temp_dir_1 = tempfile.mkdtemp(prefix="reloop_repro_1_")
    temp_dir_2 = tempfile.mkdtemp(prefix="reloop_repro_2_")

    db_path_1 = os.path.join(temp_dir_1, "run1.db")
    db_path_2 = os.path.join(temp_dir_2, "run2.db")

    try:
        print("\n[Run 1/2] Executing pipeline in isolated environment 1...")
        run1 = run_pipeline_in_db(db_path_1, seed=seed, scale=scale)

        print("[Run 2/2] Executing pipeline in isolated environment 2...")
        run2 = run_pipeline_in_db(db_path_2, seed=seed, scale=scale)

        table_comparisons = []
        all_matched = True

        for table_name, _, _ in TABLE_MODELS:
            c1 = run1["counts"].get(table_name, 0)
            c2 = run2["counts"].get(table_name, 0)
            h1 = run1["hashes"].get(table_name, "")
            h2 = run2["hashes"].get(table_name, "")

            counts_match = (c1 == c2)
            hashes_match = (h1 == h2)
            matched = counts_match and hashes_match

            if not matched:
                all_matched = False

            table_comparisons.append({
                "table_name": table_name,
                "first_run_row_count": c1,
                "second_run_row_count": c2,
                "counts_match": counts_match,
                "first_run_checksum": h1,
                "second_run_checksum": h2,
                "checksums_match": hashes_match,
                "match_status": "MATCH" if matched else "MISMATCH",
            })

        report = {
            "seed": seed,
            "dataset_scale": scale,
            "table_comparisons": table_comparisons,
            "all_tables_match": all_matched,
            "overall_reproducibility_result": "PASS" if all_matched else "FAIL",
        }

        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        print("\n" + "-" * 75)
        print(f"{'TABLE':<25} | {'RUN 1 COUNT':<12} | {'RUN 2 COUNT':<12} | {'STATUS'}")
        print("-" * 75)
        for comp in table_comparisons:
            print(f"{comp['table_name']:<25} | {comp['first_run_row_count']:<12} | {comp['second_run_row_count']:<12} | {comp['match_status']}")
        print("-" * 75)
        print(f"Overall Result: {report['overall_reproducibility_result']}")
        print(f"Report saved to: {REPORT_PATH}")

        return report

    finally:
        shutil.rmtree(temp_dir_1, ignore_errors=True)
        shutil.rmtree(temp_dir_2, ignore_errors=True)


if __name__ == "__main__":
    verify_reproducibility()
