# Local Deployment and Operations

## Requirements

- Python 3.12 (or 3.11+)
- Git
- macOS, Linux or Windows terminal

## Installation

```bash
git clone https://github.com/dheerajreddysaddi/reverse-logistics-tracker.git
cd reverse-logistics-tracker
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows PowerShell activation:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Reproduce the starter dataset

```bash
python -m scripts.reproduce_all --scale starter --seed 20261022
```

The pipeline preserves existing data. It does not reset the database. If you need a clean run, configure a separate empty database before running the pipeline.

## Start the REST API

```bash
uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```

- API root: http://127.0.0.1:8000/
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/api/v1/health

## Start the dashboard

Open a second terminal, activate the same virtual environment and run:

```bash
streamlit run src/dashboard/app.py
```

Streamlit normally opens at http://localhost:8501.

## Verify the application

```bash
curl -i http://127.0.0.1:8000/api/v1/health
pytest -v
```

The health response should return HTTP 200 and report the database connection as healthy.

## Port troubleshooting

Check whether a process is already listening before starting another server:

```bash
lsof -i :8000
lsof -i :8501
```

If a server is already running, reuse it rather than launching a duplicate. Stop a server from its own terminal with Ctrl+C. Do not terminate an unfamiliar process.

## Configuration and hosting note

The current documented setup is local SQLite development. A public deployment needs a persistent database, environment-specific database configuration, secrets management, and a deployment-specific security review. Do not publish a local SQLite file or credentials, and do not expose a development server directly to the public internet.
