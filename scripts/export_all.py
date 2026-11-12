"""
Automated Data Export Engine for Reverse Logistics Control Tower.

Exports all 10 core entities + operational_exceptions to:
- CSV: data/exports/csv/{table_name}.csv
- JSON: data/exports/json/{table_name}.json
- SQL: data/exports/sql/seed_data.sql
"""

import csv
import json
import os
import sqlite3
from typing import Dict, Any, List

from src.database.connection import DATABASE_PATH, SessionLocal
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BASE_DIR, "data", "exports")
CSV_DIR = os.path.join(EXPORTS_DIR, "csv")
JSON_DIR = os.path.join(EXPORTS_DIR, "json")
SQL_DIR = os.path.join(EXPORTS_DIR, "sql")

TABLES = [
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


def export_all():
    os.makedirs(CSV_DIR, exist_ok=True)
    os.makedirs(JSON_DIR, exist_ok=True)
    os.makedirs(SQL_DIR, exist_ok=True)

    db = SessionLocal()
    print("=" * 60)
    print(" EXPORTING ALL CORE ENTITIES (CSV, JSON, SQL)")
    print("=" * 60)

    try:
        # Export CSV and JSON for each entity
        for table_name, model, pk_col in TABLES:
            rows = db.query(model).order_by(getattr(model, pk_col)).all()
            records = []
            for row in rows:
                record = {}
                for col in model.__table__.columns:
                    val = getattr(row, col.name)
                    record[col.name] = str(val) if val is not None else None
                records.append(record)

            # Write JSON
            json_file = os.path.join(JSON_DIR, f"{table_name}.json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)

            # Write CSV
            csv_file = os.path.join(CSV_DIR, f"{table_name}.csv")
            if records:
                fieldnames = list(records[0].keys())
                with open(csv_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(records)

            print(f"Exported {table_name:<25}: {len(records):>5} rows -> CSV & JSON")

        # Export SQL Dump
        sql_file = os.path.join(SQL_DIR, "seed_data.sql")
        conn = sqlite3.connect(DATABASE_PATH)
        with open(sql_file, "w", encoding="utf-8") as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")
        conn.close()
        print(f"\nExported complete database SQL seed dump -> {sql_file}")

    finally:
        db.close()


if __name__ == "__main__":
    export_all()
