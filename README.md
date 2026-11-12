# Reverse Logistics & Asset Custody Tracking System

An end-to-end platform for reusable asset lifecycle management, shipment tracking, custody reconstruction, returns, inspections, repairs, deposit settlement, and anomaly detection.

## Features
- Deterministic synthetic data generation
- Asset, shipment, and custody tracking
- Return authorizations, inspections, and repairs
- Deposit refund and adjustment calculations
- Five-rule anomaly detection and evaluation metrics
- FastAPI REST API and Streamlit dashboard
- Automated tests and reproducible pipeline

## Technology Stack
Python 3.11, Pandas, NumPy, Faker, SQLite, SQLAlchemy, FastAPI, Pydantic, Uvicorn, Streamlit, Pytest, HTTPX, and Git.

## Architecture
1. Data generation
2. SQLite database and SQLAlchemy models
3. Business services for custody, returns, deposits, and anomaly detection
4. FastAPI REST API
5. Streamlit dashboard

## Database Entities
Owner, Location, AssetType, ReusableAsset, Shipment, CustodyEvent, ReturnAuthorization, Inspection, Repair, and DepositLedger.

## Installation
```bash
git clone https://github.com/dheerajreddysaddi/reverse-logistics-tracker.git
cd reverse-logistics-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Reproduction Pipeline
```bash
python -m scripts.reproduce_all --scale starter --seed 20261022
python -m scripts.reproduce_all --scale full --seed 20261022
```
The pipeline seeds master data, generates operational records, detects anomalies, and evaluates results. Existing database records are preserved. The script does not automatically reset or delete the database. Use a separate fresh database for a clean reproduction.

## Run the API
```bash
uvicorn src.api.main:app --reload
```
API: http://127.0.0.1:8000
Swagger: http://127.0.0.1:8000/docs

## Run the Dashboard
```bash
streamlit run src/dashboard/app.py
```

## API Endpoints
All versioned routes use `/api/v1`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Database health |
| GET | `/api/v1/assets` | Paginated asset list |
| GET | `/api/v1/assets/{asset_identifier}` | Asset details |
| GET | `/api/v1/assets/{asset_identifier}/trajectory` | Custody history |
| POST | `/api/v1/events` | Ingest custody event |
| GET | `/api/v1/rmas` | Return authorizations |
| GET | `/api/v1/anomalies` | Detect anomalies |
| GET | `/api/v1/evaluation/metrics` | Evaluation report |

## Inspection and Deposit Rules
Composite score = `(Cosmetic x 0.4) + (Functional x 0.6)`.

| Grade | Score | Condition | Action | Deposit |
|---|---:|---|---|---|
| A | >= 8.5 | Good | Restock | 100% refund |
| B | >= 6.5 | Good | Restock | 90% refund |
| C | >= 4.0 | Damaged | Refurbish | 50% refund |
| F | Below 4.0 | Unusable | Scrap | Forfeited |

## Anomaly Detection Rules
- ANOM-01: Impossible travel speed
- ANOM-02: Receipt without shipment
- ANOM-03: Refund before inspection
- ANOM-04: Refund exceeds original deposit
- ANOM-05: Asset assigned to multiple active shipments

## Evaluation
The engine calculates TP, FP, TN, FN, accuracy, precision, recall, specificity, and F1. Reports are saved in `data/processed/`.

Current controlled synthetic benchmark: 500 assets, 10 anomalies, 490 clean assets, TP=10, FP=0, FN=0, TN=490. Accuracy, precision, recall, specificity, and F1 are each 100%. These results apply only to the current synthetic benchmark, not guaranteed real-world performance.

## Automated Tests
```bash
pytest -v
```
Latest result: **17 passed, 2 dependency deprecation warnings**.

## Current Starter Database
| Record | Count |
|---|---:|
| Assets | 500 |
| Shipments | 254 |
| Custody events | 647 |
| Return authorizations | 100 |
| Inspections | 102 |
| Repairs | 24 |
| Deposit ledger entries | 101 |

Counts describe the current local database and may change.

## Interview Walkthrough
**Problem:** Organizations need visibility into reusable asset location, custody, returns, repairs, and deposits.

**Solution:** The platform tracks assets and shipments, reconstructs custody histories, manages return inspections, calculates settlements, and detects operational anomalies.

**Implementation:** Python and SQLAlchemy handle data and business logic; SQLite stores records; FastAPI exposes endpoints; Streamlit provides dashboards; Pytest validates functionality.

## Objective
Provide operational visibility, asset traceability, automated exception detection, and financial accountability across the reusable asset return lifecycle.
