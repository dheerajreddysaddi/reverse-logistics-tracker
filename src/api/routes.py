
"""
FastAPI route handlers for the Reverse Logistics system.
All database fields match src/database/models.py.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status as http_status,
)
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.database.connection import get_db

from src.database.models import (
    ReusableAsset,
    AssetType,
    Owner,
    Location,
    Shipment,
    CustodyEvent,
    ReturnAuthorization,
    Inspection,
    Repair,
)

from src.services.custody_service import CustodyService
from src.services.anomaly_detector import AnomalyDetector
from src.services.evaluation_metrics import EvaluationEngine

from src.api.schemas import (
    HealthResponse,
    AssetSummary,
    AssetDetail,
    TrajectoryResponse,
    CustodyEventCreate,
    CustodyEventResponse,
    RMAResponse,
    AnomalyItem,
)

router = APIRouter()


def find_asset(db: Session, identifier: str):
    """
    Find an asset using either its integer ID or asset code.
    Example: 251 or AST-000251.
    """

    if identifier.isdigit():
        return (
            db.query(ReusableAsset)
            .filter(
                ReusableAsset.asset_id == int(identifier)
            )
            .first()
        )

    return (
        db.query(ReusableAsset)
        .filter(
            ReusableAsset.asset_code == identifier
        )
        .first()
    )


# ---------------------------------------------------------
# 1. HEALTH CHECK
# ---------------------------------------------------------

@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
)
def get_system_health(db: Session = Depends(get_db)):
    """Check database connectivity and system record counts."""

    try:
        db.execute(text("SELECT 1"))

        return {
            "status": "HEALTHY",
            "database_connected": True,
            "total_assets": db.query(ReusableAsset).count(),
            "total_shipments": db.query(Shipment).count(),
            "total_custody_events": db.query(CustodyEvent).count(),
            "total_rmas": db.query(ReturnAuthorization).count(),
        }

    except Exception as error:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(error)}",
        )


# ---------------------------------------------------------
# 2. ASSET LIST
# ---------------------------------------------------------

@router.get(
    "/assets",
    response_model=List[AssetSummary],
    tags=["Assets"],
)
def list_assets(
    status: Optional[str] = Query(None, description="Filter by lifecycle status"),
    asset_type_id: Optional[int] = Query(None, description="Filter by asset type ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Return a paginated list of reusable assets."""

    query = db.query(ReusableAsset)

    if status:
        query = query.filter(ReusableAsset.lifecycle_status == status)

    if asset_type_id is not None:
        query = query.filter(ReusableAsset.asset_type_id == asset_type_id)

    offset = (page - 1) * page_size

    assets = (
        query.order_by(ReusableAsset.asset_id)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    results = []

    for asset in assets:
        asset_type = db.query(AssetType).filter(
            AssetType.asset_type_id == asset.asset_type_id
        ).first()

        results.append({
            "asset_id": asset.asset_id,
            "asset_code": asset.asset_code,
            "serial_number": asset.serial_number,
            "asset_type_name": asset_type.type_name if asset_type else "Unknown",
            "lifecycle_status": asset.lifecycle_status,
            "deposit_amount": float(asset_type.deposit_amount or 0) if asset_type else 0.0,
            "created_at": asset.created_at,
        })

    return results

# ---------------------------------------------------------
# 3. ASSET DETAIL
# ---------------------------------------------------------

@router.get(
    "/assets/{asset_identifier}",
    response_model=AssetDetail,
    tags=["Assets"],
)
def get_asset_detail(
    asset_identifier: str,
    db: Session = Depends(get_db),
):
    """Return detailed information about one asset."""

    asset = find_asset(db, asset_identifier)

    if not asset:
        raise HTTPException(
            status_code=404,
            detail=f"Asset {asset_identifier} not found",
        )

    asset_type = db.query(AssetType).filter(
        AssetType.asset_type_id == asset.asset_type_id
    ).first()

    owner = db.query(Owner).filter(
        Owner.owner_id == asset.owner_id
    ).first()

    latest_event = (
        db.query(CustodyEvent)
        .filter(CustodyEvent.asset_id == asset.asset_id)
        .order_by(
            CustodyEvent.event_timestamp.desc(),
            CustodyEvent.event_id.desc(),
        )
        .first()
    )

    current_location_name = None
    last_event_time = None

    if latest_event:
        location = db.query(Location).filter(
            Location.location_id == latest_event.to_location_id
        ).first()

        current_location_name = (
            location.location_name if location else "Unknown"
        )

        last_event_time = latest_event.event_timestamp

    return {
        "asset_id": asset.asset_id,
        "asset_code": asset.asset_code,
        "serial_number": asset.serial_number,
        "asset_type_name": (
            asset_type.type_name if asset_type else "Unknown"
        ),
        "lifecycle_status": asset.lifecycle_status,
        "deposit_amount": float(
            asset_type.deposit_amount or 0
        ) if asset_type else 0.0,
        "created_at": asset.created_at,
        "owner_name": owner.owner_name if owner else None,
        "current_location_name": current_location_name,
        "last_event_time": last_event_time,
    }


# ---------------------------------------------------------
# 4. ASSET CUSTODY TRAJECTORY
# ---------------------------------------------------------

@router.get(
    "/assets/{asset_identifier}/trajectory",
    response_model=TrajectoryResponse,
    tags=["Custody Trajectory"],
)
def get_asset_trajectory(
    asset_identifier: str,
    db: Session = Depends(get_db),
):
    """Reconstruct the asset's complete custody history."""

    asset = find_asset(db, asset_identifier)

    if not asset:
        raise HTTPException(
            status_code=404,
            detail=f"Asset {asset_identifier} not found",
        )

    trajectory_data = CustodyService.get_asset_trajectory(
        db,
        asset.asset_id,
    )

    if not trajectory_data:
        raise HTTPException(
            status_code=404,
            detail="Custody trajectory not found",
        )

    return {
        "asset_id": trajectory_data["asset_id"],
        "asset_code": trajectory_data["asset_code"],
        "serial_number": trajectory_data["serial_number"],
        "lifecycle_status": trajectory_data["lifecycle_status"],
        "current_location": trajectory_data["current_location"],
        "current_location_description": (
            trajectory_data["current_location_description"]
        ),
        "is_in_transit": trajectory_data["is_in_transit"],
        "current_custodian": trajectory_data["current_custodian"],
        "last_event_time": trajectory_data["last_event_time"],
        "total_events": trajectory_data["total_events"],
        "trajectory": trajectory_data["trajectory"],
    }


# ---------------------------------------------------------
# 5. REAL-TIME CUSTODY EVENT INGESTION
# ---------------------------------------------------------

@router.post(
    "/events",
    response_model=CustodyEventResponse,
    status_code=http_status.HTTP_201_CREATED,
    tags=["Custody Ingestion"],
)
def ingest_custody_event(
    event_in: CustodyEventCreate,
    db: Session = Depends(get_db),
):
    """Accept a new custody scan and store it in the database."""

    asset = db.query(ReusableAsset).filter(
        ReusableAsset.asset_id == event_in.asset_id
    ).first()

    if not asset:
        raise HTTPException(
            status_code=404,
            detail=f"Asset ID {event_in.asset_id} does not exist",
        )

    destination = db.query(Location).filter(
        Location.location_id == event_in.to_location_id
    ).first()

    if not destination:
        raise HTTPException(
            status_code=404,
            detail="Destination location does not exist",
        )

    if event_in.from_location_id is not None:
        origin = db.query(Location).filter(
            Location.location_id == event_in.from_location_id
        ).first()

        if not origin:
            raise HTTPException(
                status_code=404,
                detail="Origin location does not exist",
            )

    if event_in.shipment_id is not None:
        shipment = db.query(Shipment).filter(
            Shipment.shipment_id == event_in.shipment_id
        ).first()

        if not shipment:
            raise HTTPException(
                status_code=404,
                detail="Shipment does not exist",
            )

    new_event = CustodyEvent(
        asset_id=asset.asset_id,
        shipment_id=event_in.shipment_id,
        from_location_id=event_in.from_location_id,
        to_location_id=event_in.to_location_id,
        actor_name=event_in.actor_name,
        event_type=event_in.event_type,
        event_timestamp=datetime.utcnow(),
        notes=event_in.notes,
    )

    try:
        db.add(new_event)
        db.commit()
        db.refresh(new_event)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save custody event",
        )

    return {
        "event_id": new_event.event_id,
        "asset_id": new_event.asset_id,
        "event_type": new_event.event_type,
        "event_timestamp": new_event.event_timestamp,
        "actor_name": new_event.actor_name,
        "status": "INGESTED",
    }


# ---------------------------------------------------------
# 6. RETURN AUTHORIZATIONS
# ---------------------------------------------------------

@router.get(
    "/rmas",
    response_model=List[RMAResponse],
    tags=["Reverse Logistics"],
)
def list_rmas(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return RMA records with inspection and repair information."""

    rmas = (
        db.query(ReturnAuthorization)
        .order_by(ReturnAuthorization.request_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []

    for rma in rmas:

        inspection = (
            db.query(Inspection)
            .filter(Inspection.return_id == rma.return_id)
            .order_by(Inspection.inspection_date.desc())
            .first()
        )

        repair_status = None

        if inspection:
            repair = (
                db.query(Repair)
                .filter(
                    Repair.inspection_id == inspection.inspection_id
                )
                .first()
            )

            if repair:
                repair_status = repair.repair_status

        results.append({
            "return_id": rma.return_id,
            "return_code": rma.return_code,
            "asset_id": rma.asset_id,
            "shipment_id": rma.shipment_id,
            "requested_by": rma.requested_by,
            "request_date": rma.request_date,
            "approved_date": rma.approved_date,
            "return_status": rma.return_status,
            "inspection_condition": (
                inspection.condition_status if inspection else None
            ),
            "inspection_remarks": (
                inspection.remarks if inspection else None
            ),
            "repair_status": repair_status,
        })

    return results


# ---------------------------------------------------------
# 7. ANOMALY DETECTION
# ---------------------------------------------------------

@router.get(
    "/anomalies",
    response_model=List[AnomalyItem],
    tags=["Anomalies & Compliance"],
)
def get_active_anomalies(db: Session = Depends(get_db)):
    """Run the five anomaly detection rules across the fleet."""

    return AnomalyDetector.scan_all(db)


# ---------------------------------------------------------
# 8. EVALUATION METRICS
# ---------------------------------------------------------

@router.get(
    "/evaluation/metrics",
    tags=["Anomalies & Compliance"],
)
def get_evaluation_metrics(db: Session = Depends(get_db)):
    """Return the current evaluation scorecard."""

    return EvaluationEngine.evaluate(db)
