from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.connection import SessionLocal
from src.database.models import (
    Owner,
    Location,
    AssetType,
    ReusableAsset,
    CustodyEvent,
)
from src.generator.id_generator import (
    generate_asset_id,
    generate_serial_number,
    generate_shipment_id,
    generate_rma_number,
)
from src.services.custody_service import CustodyService
from src.services.reverse_logistics_service import ReverseLogisticsService
from src.services.evaluation_metrics import EvaluationEngine


client = TestClient(app)


@pytest.fixture
def db():
    """Open a database session without modifying existing records."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_asset_with_custody(db):
    """Find an existing asset that has at least one custody event."""
    event = (
        db.query(CustodyEvent)
        .order_by(CustodyEvent.asset_id)
        .first()
    )

    assert event is not None, "No custody events found in the database."

    asset = (
        db.query(ReusableAsset)
        .filter(ReusableAsset.asset_id == event.asset_id)
        .first()
    )

    assert asset is not None
    return asset


# 1. Master data validation
def test_master_data_exists(db):
    assert db.query(Owner).count() >= 3
    assert db.query(Location).count() >= 4
    assert db.query(AssetType).count() >= 5


# 2. Deterministic ID generation
def test_deterministic_id_generation():
    assert generate_asset_id(1) == "AST-000001"
    assert generate_shipment_id(1) == "SHP-000001"
    assert generate_rma_number(1) == "RMA-2026-000001"

    first = generate_serial_number("Reusable Container", 1)
    second = generate_serial_number("Reusable Container", 1)

    assert first == second
    assert first.startswith("SN-")


# 3. Inspection grading logic
@pytest.mark.parametrize(
    "cosmetic,functional,expected_grade,expected_condition,expected_action",
    [
        (10, 10, "A", "good", "restock"),
        (8, 8, "B", "good", "restock"),
        (5, 5, "C", "damaged", "refurbish"),
        (2, 2, "F", "unusable", "scrap"),
    ],
)
def test_inspection_evaluation(
    cosmetic,
    functional,
    expected_grade,
    expected_condition,
    expected_action,
):
    result = ReverseLogisticsService.evaluate_inspection(
        cosmetic,
        functional,
    )

    assert result == (
        expected_grade,
        expected_condition,
        expected_action,
    )


# 4. Deposit settlement calculations
@pytest.mark.parametrize(
    "grade,expected_type,expected_amount",
    [
        ("A", "refund", Decimal("1000.00")),
        ("B", "refund", Decimal("900.00")),
        ("C", "refund", Decimal("500.00")),
        ("F", "adjustment", Decimal("1000.00")),
    ],
)
def test_deposit_settlement(grade, expected_type, expected_amount):
    transaction_type, amount, note = (
        ReverseLogisticsService.calculate_deposit_settlement(
            Decimal("1000.00"),
            grade,
        )
    )

    assert transaction_type == expected_type
    assert amount == expected_amount
    assert isinstance(note, str)
    assert note


def test_zero_deposit_settlement():
    transaction_type, amount, note = (
        ReverseLogisticsService.calculate_deposit_settlement(
            Decimal("0.00"),
            "A",
        )
    )

    assert transaction_type is None
    assert amount == Decimal("0.00")
    assert "No security deposit" in note


# 5. Custody trajectory reconstruction
def test_custody_trajectory_reconstruction(db):
    asset = get_asset_with_custody(db)

    trajectory = CustodyService.get_asset_trajectory(
        db,
        asset.asset_id,
    )

    assert trajectory is not None
    assert trajectory["asset_id"] == asset.asset_id
    assert trajectory["asset_code"] == asset.asset_code
    assert trajectory["total_events"] > 0
    assert len(trajectory["trajectory"]) > 0


# 6. Anomaly detection and evaluation metrics
def test_anomaly_evaluation_and_f1_score(db):
    report = EvaluationEngine.evaluate(db)

    assert "confusion_matrix" in report
    assert "aggregate_metrics" in report
    assert "rule_breakdown" in report

    metrics = report["aggregate_metrics"]

    assert "f1_score" in metrics
    assert 0.0 <= metrics["f1_score"] <= 1.0
    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0

    assert report["dataset_summary"]["total_evaluated_assets"] > 0


# 7. FastAPI health endpoint
def test_api_health():
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "HEALTHY"
    assert data["database_connected"] is True
    assert data["total_assets"] >= 1


# 8. FastAPI asset list and trajectory endpoints
def test_api_asset_list():
    response = client.get(
        "/api/v1/assets",
        params={"page": 1, "page_size": 5},
    )

    assert response.status_code == 200

    assets = response.json()

    assert isinstance(assets, list)
    assert len(assets) <= 5
    assert len(assets) > 0
    assert "asset_code" in assets[0]


def test_api_asset_trajectory(db):
    asset = get_asset_with_custody(db)

    response = client.get(
        f"/api/v1/assets/{asset.asset_code}/trajectory"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["asset_id"] == asset.asset_id
    assert data["asset_code"] == asset.asset_code
    assert data["total_events"] > 0
    assert len(data["trajectory"]) > 0


# 9. FastAPI anomaly endpoint
def test_api_anomaly_endpoint():
    response = client.get("/api/v1/anomalies")

    assert response.status_code == 200

    anomalies = response.json()

    assert isinstance(anomalies, list)
    assert len(anomalies) >= 1

    if anomalies:
        assert "rule_code" in anomalies[0]
        assert "asset_id" in anomalies[0]
        assert "severity" in anomalies[0]


# 10. Automated Data Validation Engine (12 Checks)
def test_validation_engine_all_checks(db):
    from src.services.validation_engine import ValidationEngine
    report = ValidationEngine.run_all_checks(db)

    assert report["total_checks"] == 12
    assert report["passed_checks"] >= 10
    assert report["data_quality_percentage"] >= 90.0
    assert "checks" in report
    assert len(report["checks"]) == 12


# 11. Lifecycle Engine Transition Rules
def test_lifecycle_engine_rules():
    from src.services.lifecycle_engine import LifecycleEngine

    # Valid transitions
    ok_avail, _ = LifecycleEngine.validate_transition("available", "dispatched")
    assert ok_avail is True

    ok_transit, _ = LifecycleEngine.validate_transition("in_transit", "delivered")
    assert ok_transit is True

    # Invalid: lost asset cannot be dispatched
    ok_lost, reason_lost = LifecycleEngine.validate_transition("lost", "dispatched")
    assert ok_lost is False
    assert "Lost assets cannot be dispatched" in reason_lost

    # Invalid: retired asset cannot be dispatched
    ok_ret, reason_ret = LifecycleEngine.validate_transition("retired", "in_transit")
    assert ok_ret is False

    # Outstanding days formula test
    from datetime import datetime, timedelta
    ref = datetime(2026, 10, 22)
    exp = datetime(2026, 10, 15)
    days = LifecycleEngine.calculate_days_outstanding(ref, exp)
    assert days == 7


# 12. Operational Exception Resolution
def test_exception_resolution(db):
    from src.services.anomaly_detector import AnomalyDetector
    anomalies = AnomalyDetector.scan_all(db, sync_exceptions_table=True)
    assert len(anomalies) >= 5

    first_exc = anomalies[0]["exception_id"]
    updated = AnomalyDetector.resolve_exception(
        db,
        first_exc,
        "Under Review",
        "Assigned to compliance officer",
    )
    assert updated is True

