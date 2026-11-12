# Design Decisions

## 1. Application architecture

The project uses a layered monolithic architecture:
- SQLAlchemy models and sessions manage persistence.
- Service modules contain custody, reverse-logistics, anomaly and evaluation logic.
- FastAPI exposes the domain through versioned REST endpoints.
- Streamlit provides an operational dashboard.
- A master reproduction script coordinates deterministic synthetic data generation and evaluation.

This keeps the project straightforward to run and explain while separating interface code from business rules.

## 2. Persistence

SQLite is used for the local project database to keep setup lightweight. SQLAlchemy provides a consistent model/session layer. Monetary fields use SQL `NUMERIC(12, 2)` rather than binary floating-point storage.

The reproduction pipeline deliberately preserves existing records. It does not silently reset or delete the database. For a clean experiment, use a separate database file and follow the generator instructions.

## 3. Asset and event identity

Assets and shipments have integer database primary keys and unique human-readable codes. Deterministic ID helpers make generated business identifiers repeatable for a fixed sequence.

Custody history is stored as timestamped events associated with an asset. The trajectory service orders events and derives the latest recorded location and custodian from the event history.

## 4. Inspection and deposit policy

Inspection grade is derived from cosmetic and functional scores using a weighted composite:
`composite = cosmetic × 0.4 + functional × 0.6`.

| Grade | Composite score | Condition | Disposition | Deposit settlement |
|---|---:|---|---|---:|
| A | >= 8.5 | Good | Restock | 100% refund |
| B | >= 6.5 | Good | Restock | 90% refund |
| C | >= 4.0 | Damaged | Refurbish | 50% refund |
| F | Below 4.0 | Unusable | Scrap | Full deposit adjustment |

The service handles a zero-deposit case without creating a monetary transaction.

## 5. Anomaly detection

The anomaly detector implements five explicit operational rules:
- ANOM-01: impossible travel speed.
- ANOM-02: receipt without shipment.
- ANOM-03: refund before inspection.
- ANOM-04: refund exceeds original deposit.
- ANOM-05: asset assigned to multiple active shipments.

Rules are explainable and return rule identifiers, severity and supporting details. They are intended to surface operational exceptions for review, not make autonomous fraud or misconduct determinations.

## 6. Evaluation and interpretation

The evaluation module computes a confusion matrix and accuracy, precision, recall, specificity and F1, both overall and per rule. The current benchmark uses synthetic anomalies deliberately inserted into generated records. Perfect scores on this controlled dataset show that the known injected scenarios were recovered; they do not establish performance on live logistics data.

## 7. API and dashboard responsibilities

FastAPI owns HTTP request/response validation and exposes Swagger/ReDoc documentation. Streamlit reads the database and calls domain services to present the operational views. Business calculations should remain in service modules so that the API, dashboard and tests can use the same logic.

## 8. Testing strategy

The automated suite covers master data, deterministic identifiers, inspection grading, deposit settlement, custody reconstruction, evaluation metrics and API endpoints. Tests use the configured project database; use a disposable test database when extending tests that write records.
