# Source and Data Manifest

## Data Provenance
All data utilized across this platform is completely synthetic, deterministically generated locally by `src/generator/data_generator.py` using fixed random seed `20261022`. 

- **No Real Personal or Commercial Data:** No customer information, real employee names, proprietary carrier routes, or live production supply chain data are processed or stored in this repository.
- **Fictional Identifiers:** 
  - Asset IDs follow standard zero-padded alphanumeric format: `ASSET-0000001` through `ASSET-0020000`.
  - Return authorizations use formatted serials: `RMA-2026-000001`.
  - Shipments follow carrier format: `SHP-2026-000001`.
  - Custody events use compound traceability keys: `CUST-ASSET-0000001-000001`.
- **Entity Names & Facilities:** Company names, carrier identifiers (e.g. Apex Freight, Blue Dart Logistics, Titan Transport), and facility coordinates are synthetic representations designed to model realistic distribution hub geography across India and global supply chains.

## Controlled Benchmark Generation
The generator supports two standardized scale configurations:
1. **Starter Mode (Default):** 500 reusable assets, 250 shipments, and 2,500 custody events (suitable for instant cloud spin-up, automated tests, and interactive exploration).
2. **Full Scale Mode:** 20,000 reusable assets, 10,000 shipments, and 100,000 custody events (designed for high-volume stress testing and benchmark validation).

In both modes, parent master entities (`owners`, `locations`, `asset_types`) are seeded prior to dependent transactional records. Operational anomalies are injected via controlled deterministic routines and simultaneously recorded to `data/processed/ground_truth.json` and `data/processed/ground_truth.csv` to ensure ground-truth isolation from the detection engine.

## Software Dependencies (Pinned in `requirements.txt`)
All dependencies are standard open-source Python libraries distributed via PyPI:
- `streamlit`: Enterprise presentation layer and interactive web dashboards.
- `fastapi` & `uvicorn`: High-performance asynchronous REST API framework.
- `sqlalchemy`: Relational Object-Relational Mapping (ORM) and Core SQL expression engine.
- `pydantic`: Runtime data validation and schema enforcement.
- `pandas` & `numpy`: High-performance tabular data manipulation and numerical array processing.
- `plotly` & `folium`: Data visualization and geospatial GIS mapping.
- `pytest` & `httpx`: Automated testing framework and HTTP test client.
- `faker`: Deterministic synthetic entity attribute generation.
