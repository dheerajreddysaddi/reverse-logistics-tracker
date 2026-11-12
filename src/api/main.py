
"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router


app = FastAPI(
    title="Reverse Logistics & Asset Custody Tracking API",
    description=(
        "REST API for reusable asset lifecycle management, "
        "shipment tracking, custody reconstruction, reverse "
        "logistics, deposit reconciliation and anomaly detection."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow frontend applications to access the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register versioned API endpoints.
app.include_router(
    router,
    prefix="/api/v1",
)


@app.get("/", tags=["System"])
def root():
    return {
        "service": "Reverse Logistics & Asset Custody API",
        "version": "1.0.0",
        "status": "running",
        "documentation": "/docs",
    }
