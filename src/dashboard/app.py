"""
Streamlit Operational Dashboard
Reverse Logistics & Asset Custody Tracking Platform
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import re
import pandas as pd
import streamlit as st

from sqlalchemy import func

from src.database.connection import SessionLocal
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
    DepositLedger,
)

from src.services.custody_service import CustodyService
from src.services.anomaly_detector import AnomalyDetector
from src.services.evaluation_metrics import EvaluationEngine


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Reverse Logistics Control Tower",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📦 Reverse Logistics Control Tower")
st.caption(
    "Enterprise Asset Custody | Reverse Logistics | "
    "Anomaly Monitoring"
)


# --------------------------------------------------
# DATABASE HELPER
# --------------------------------------------------

def get_overview_data():
    db = SessionLocal()

    try:
        total_assets = db.query(ReusableAsset).count()

        active_shipments = db.query(Shipment).filter(
            Shipment.shipment_status.in_(["planned", "dispatched"])
        ).count()

        total_shipments = db.query(Shipment).count()
        total_rmas = db.query(ReturnAuthorization).count()
        total_repairs = db.query(Repair).count()

        total_refunds = (
            db.query(func.sum(DepositLedger.amount))
            .filter(DepositLedger.transaction_type == "refund")
            .scalar()
            or 0
        )

        total_forfeitures = (
            db.query(func.sum(DepositLedger.amount))
            .filter(DepositLedger.transaction_type == "adjustment")
            .scalar()
            or 0
        )

        status_data = (
            db.query(
                ReusableAsset.lifecycle_status,
                func.count(ReusableAsset.asset_id),
            )
            .group_by(ReusableAsset.lifecycle_status)
            .all()
        )

        status_df = pd.DataFrame(
            status_data,
            columns=["Lifecycle Status", "Assets"],
        )

        category_data = (
            db.query(
                AssetType.type_name,
                func.count(ReusableAsset.asset_id),
            )
            .join(
                ReusableAsset,
                ReusableAsset.asset_type_id == AssetType.asset_type_id,
            )
            .group_by(AssetType.type_name)
            .all()
        )

        category_df = pd.DataFrame(
            category_data,
            columns=["Asset Category", "Assets"],
        )

        shipment_data = (
            db.query(
                Shipment.shipment_status,
                func.count(Shipment.shipment_id),
            )
            .group_by(Shipment.shipment_status)
            .all()
        )

        shipment_df = pd.DataFrame(
            shipment_data,
            columns=["Shipment Status", "Shipments"],
        )

        return {
            "total_assets": total_assets,
            "active_shipments": active_shipments,
            "total_shipments": total_shipments,
            "total_rmas": total_rmas,
            "total_repairs": total_repairs,
            "total_refunds": float(total_refunds),
            "total_forfeitures": float(total_forfeitures),
            "status_df": status_df,
            "category_df": category_df,
            "shipment_df": shipment_df,
        }

    finally:
        db.close()


def extract_grade(remarks):
    """Extract Grade A/B/C/F from inspection remarks."""

    if not remarks:
        return "Not recorded"

    match = re.search(
        r"\bGrade\s*([ABCF])\b",
        remarks,
        re.IGNORECASE,
    )

    if match:
        return "Grade " + match.group(1).upper()

    return "Not recorded"


# --------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------

st.sidebar.title("📦 Logistics Hub")
st.sidebar.caption("Reverse Logistics & Asset Custody Platform")

view = st.sidebar.radio(
    "Dashboard Navigation",
    [
        "Executive Overview",
        "Asset Trajectory Explorer",
        "Reverse Logistics & RMAs",
        "Anomaly Center & Metrics",
    ],
)

st.sidebar.divider()
st.sidebar.success("System Status: ONLINE")
st.sidebar.info("Database: SQLite\nBackend: SQLAlchemy + FastAPI")


# --------------------------------------------------
# VIEW 1: EXECUTIVE OVERVIEW
# --------------------------------------------------

if view == "Executive Overview":

    st.header("📊 Executive Fleet & Operations Overview")

    st.write(
        "Monitor reusable assets, shipment activity, "
        "reverse logistics and financial settlements."
    )

    stats = get_overview_data()

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "Tracked Assets",
        f"{stats['total_assets']:,}",
    )

    col2.metric(
        "Active Shipments",
        f"{stats['active_shipments']:,}",
    )

    col3.metric(
        "Total RMAs",
        f"{stats['total_rmas']:,}",
    )

    col4.metric(
        "Repairs",
        f"{stats['total_repairs']:,}",
    )

    col5.metric(
        "Refunded Deposits",
        f"₹{stats['total_refunds']:,.2f}",
    )

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Asset Lifecycle Distribution")

        if not stats["status_df"].empty:
            st.bar_chart(
                stats["status_df"].set_index("Lifecycle Status")
            )
        else:
            st.info("No asset status data available.")

    with right:
        st.subheader("Inventory by Asset Category")

        if not stats["category_df"].empty:
            st.bar_chart(
                stats["category_df"].set_index("Asset Category")
            )
        else:
            st.info("No asset category data available.")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Shipment Status Distribution")

        if not stats["shipment_df"].empty:
            st.bar_chart(
                stats["shipment_df"].set_index("Shipment Status")
            )
        else:
            st.info("No shipment data available.")

    with right:
        st.subheader("Financial Settlement Summary")

        financial_df = pd.DataFrame(
            {
                "Settlement": ["Refunds", "Forfeitures"],
                "Amount (₹)": [
                    stats["total_refunds"],
                    stats["total_forfeitures"],
                ],
            }
        )

        st.bar_chart(
            financial_df.set_index("Settlement")
        )

    st.caption(
        f"Total shipments recorded: {stats['total_shipments']:,}"
    )


# --------------------------------------------------
# VIEW 2: ASSET TRAJECTORY EXPLORER
# --------------------------------------------------

elif view == "Asset Trajectory Explorer":

    st.header("🛰️ Asset Trajectory & Custody Explorer")

    st.write(
        "Search an asset and inspect its reconstructed "
        "location, custodian and chronological movement history."
    )

    db = SessionLocal()

    try:
        asset_records = (
            db.query(
                ReusableAsset.asset_id,
                ReusableAsset.asset_code,
            )
            .order_by(ReusableAsset.asset_id)
            .all()
        )

        locations = db.query(Location).all()

        location_lookup = {
            location.location_name: location
            for location in locations
        }

        max_asset_id = (
            db.query(func.max(ReusableAsset.asset_id)).scalar() or 1
        )

    finally:
        db.close()

    if not asset_records:
        st.warning("No assets are available.")
    else:
        asset_options = {
            f"{asset.asset_code} (ID: {asset.asset_id})": asset.asset_id
            for asset in asset_records
        }

        selected_label = st.selectbox(
            "Select an asset",
            list(asset_options.keys()),
        )

        selected_asset_id = asset_options[selected_label]

        db = SessionLocal()

        try:
            recon = CustodyService.get_asset_trajectory(
                db,
                selected_asset_id,
            )

            asset = (
                db.query(ReusableAsset)
                .filter(
                    ReusableAsset.asset_id == selected_asset_id
                )
                .first()
            )

            asset_type = (
                db.query(AssetType)
                .filter(
                    AssetType.asset_type_id == asset.asset_type_id
                )
                .first()
            )

        finally:
            db.close()

        if recon:

            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Asset ID", recon["asset_id"])
            col2.metric("Asset Code", recon["asset_code"])
            col3.metric(
                "Lifecycle Status",
                recon["lifecycle_status"],
            )
            col4.metric(
                "Total Custody Events",
                recon["total_events"],
            )

            st.info(
                f"**Current Location:** "
                f"{recon['current_location_description']}"
            )

            col1, col2 = st.columns(2)

            col1.write(
                f"**Current Custodian:** {recon['current_custodian']}"
            )

            col2.write(
                f"**Asset Category:** "
                f"{asset_type.type_name if asset_type else 'Unknown'}"
            )

            st.write(
                f"**Last Event:** "
                f"{recon['last_event_time'] or 'Not available'}"
            )

            st.divider()

            st.subheader("Chronological Chain of Custody")

            if recon["trajectory"]:

                trajectory_df = pd.DataFrame(
                    recon["trajectory"]
                )

                st.dataframe(
                    trajectory_df,
                    use_container_width=True,
                    hide_index=True,
                )

                # Build map coordinates from actual Location records.
                city_coordinates = {
                    "Hyderabad": (17.3850, 78.4867),
                    "Bengaluru": (12.9716, 77.5946),
                    "Mumbai": (19.0760, 72.8777),
                    "Chennai": (13.0827, 80.2707),
                }

                map_points = []

                for event in recon["trajectory"]:

                    location_name = event["to_location"]

                    location = location_lookup.get(location_name)

                    if location and location.city:
                        coordinates = city_coordinates.get(
                            location.city
                        )

                        if coordinates:
                            map_points.append(
                                {
                                    "lat": coordinates[0],
                                    "lon": coordinates[1],
                                }
                            )

                if map_points:
                    st.subheader("🗺️ Asset Movement Map")

                    map_df = pd.DataFrame(map_points)

                    st.map(map_df, zoom=4)

                else:
                    st.info(
                        "No mapped location coordinates are "
                        "available for this asset's events."
                    )

            else:
                st.warning(
                    "No custody events have been recorded "
                    "for this asset."
                )

        else:
            st.error("Unable to reconstruct this asset.")


# --------------------------------------------------
# VIEW 3: REVERSE LOGISTICS AND RMAs
# --------------------------------------------------

elif view == "Reverse Logistics & RMAs":

    st.header("🔄 Reverse Logistics & RMA Triage")

    st.write(
        "Analyze returned assets, inspection grades, "
        "repair costs and deposit settlements."
    )

    db = SessionLocal()

    try:
        inspections = db.query(Inspection).all()
        repairs = db.query(Repair).all()
        ledgers = db.query(DepositLedger).all()

        rmas = (
            db.query(ReturnAuthorization)
            .order_by(ReturnAuthorization.request_date.desc())
            .all()
        )

        inspection_rows = []

        for inspection in inspections:

            asset = (
                db.query(ReusableAsset)
                .filter(
                    ReusableAsset.asset_id == inspection.asset_id
                )
                .first()
            )

            inspection_rows.append(
                {
                    "Inspection ID": inspection.inspection_id,
                    "Asset Code": (
                        asset.asset_code if asset else "Unknown"
                    ),
                    "Inspector": inspection.inspector_name,
                    "Grade": extract_grade(inspection.remarks),
                    "Condition": inspection.condition_status,
                    "Inspection Date": inspection.inspection_date,
                    "Remarks": inspection.remarks,
                }
            )

        repair_rows = [
            {
                "Repair ID": repair.repair_id,
                "Asset ID": repair.asset_id,
                "Description": repair.repair_description,
                "Cost (₹)": float(repair.repair_cost),
                "Status": repair.repair_status,
            }
            for repair in repairs
        ]

        ledger_rows = [
            {
                "Asset ID": entry.asset_id,
                "Transaction": entry.transaction_type,
                "Amount (₹)": float(entry.amount),
                "Reference": entry.reference_code,
                "Date": entry.transaction_date,
            }
            for entry in ledgers
        ]

    finally:
        db.close()

    inspection_df = pd.DataFrame(inspection_rows)
    repair_df = pd.DataFrame(repair_rows)
    ledger_df = pd.DataFrame(ledger_rows)

    grades = (
        inspection_df["Grade"].value_counts().reindex(
            ["Grade A", "Grade B", "Grade C", "Grade F"],
            fill_value=0,
        )
        if not inspection_df.empty
        else pd.Series(
            [0, 0, 0, 0],
            index=["Grade A", "Grade B", "Grade C", "Grade F"],
        )
    )

    total_repair_cost = (
        sum(float(repair.repair_cost) for repair in repairs)
    )

    refund_total = sum(
        float(entry.amount)
        for entry in ledgers
        if entry.transaction_type == "refund"
    )

    forfeiture_total = sum(
        float(entry.amount)
        for entry in ledgers
        if entry.transaction_type == "adjustment"
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total RMAs", len(rmas))
    col2.metric("Inspections", len(inspections))
    col3.metric("Repairs", len(repairs))
    col4.metric("Repair Expenses", f"₹{total_repair_cost:,.2f}")

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Inspection Grade Distribution")

        grade_df = grades.rename("Units").to_frame()

        st.bar_chart(grade_df)

    with right:
        st.subheader("Inspection Condition Distribution")

        if not inspection_df.empty:
            condition_df = (
                inspection_df["Condition"]
                .value_counts()
                .rename("Units")
                .to_frame()
            )

            st.bar_chart(condition_df)
        else:
            st.info("No inspection records available.")

    st.divider()

    st.subheader("Deposit Settlement Accounting")

    col1, col2 = st.columns(2)

    col1.metric(
        "Total Refunds",
        f"₹{refund_total:,.2f}",
    )

    col2.metric(
        "Forfeitures / Adjustments",
        f"₹{forfeiture_total:,.2f}",
    )

    if not ledger_df.empty:

        settlement_df = (
            ledger_df.groupby("Transaction")["Amount (₹)"]
            .sum()
            .to_frame()
        )

        st.bar_chart(settlement_df)

        with st.expander("View Deposit Ledger"):
            st.dataframe(
                ledger_df,
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    st.subheader("Inspection Records")

    if not inspection_df.empty:
        st.dataframe(
            inspection_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No inspection records available.")

    st.subheader("Repair Records")

    if not repair_df.empty:
        st.dataframe(
            repair_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No repair records available.")

    st.subheader("Return Authorizations")

    rma_rows = [
        {
            "Return Code": rma.return_code,
            "Asset ID": rma.asset_id,
            "Requested By": rma.requested_by,
            "Request Date": rma.request_date,
            "Status": rma.return_status,
        }
        for rma in rmas
    ]

    if rma_rows:
        st.dataframe(
            pd.DataFrame(rma_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No return authorizations available.")


# --------------------------------------------------
# VIEW 4: ANOMALY CENTER AND METRICS
# --------------------------------------------------

elif view == "Anomaly Center & Metrics":

    st.header("🚨 Anomaly Center & Model Scorecard")

    st.write(
        "Monitor detected custody and financial anomalies "
        "and evaluate detection performance against ground truth."
    )

    db = SessionLocal()

    try:
        anomalies = AnomalyDetector.scan_all(db)
        report = EvaluationEngine.evaluate(db)

    finally:
        db.close()

    st.subheader(
        f"Active Anomaly Alerts: {len(anomalies)}"
    )

    if anomalies:

        anomaly_df = pd.DataFrame(anomalies)

        preferred_columns = [
            column
            for column in [
                "rule_code",
                "rule_name",
                "asset_id",
                "severity",
                "details",
            ]
            if column in anomaly_df.columns
        ]

        st.dataframe(
            anomaly_df[preferred_columns],
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.success("No anomalies detected.")

    st.divider()

    st.subheader("Empirical Model Performance Scorecard")

    metrics = report["aggregate_metrics"]

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric(
        "Accuracy",
        f"{metrics['accuracy'] * 100:.1f}%",
    )

    col2.metric(
        "Precision",
        f"{metrics['precision'] * 100:.1f}%",
    )

    col3.metric(
        "Recall",
        f"{metrics['recall'] * 100:.1f}%",
    )

    col4.metric(
        "F1-Score",
        f"{metrics['f1_score'] * 100:.1f}%",
    )

    col5.metric(
        "Specificity",
        f"{metrics['specificity'] * 100:.1f}%",
    )

    st.divider()

    st.subheader("Confusion Matrix")

    cm = report["confusion_matrix"]

    confusion_df = pd.DataFrame(
        [
            [
                cm["true_positives"],
                cm["false_negatives"],
            ],
            [
                cm["false_positives"],
                cm["true_negatives"],
            ],
        ],
        index=[
            "Actual Anomaly",
            "Actual Clean",
        ],
        columns=[
            "Predicted Anomaly",
            "Predicted Clean",
        ],
    )

    st.table(confusion_df)

    st.divider()

    st.subheader("Per-Rule Detection Performance")

    rule_rows = []

    for rule_code, rule_data in report["rule_breakdown"].items():

        rule_rows.append(
            {
                "Rule": rule_code,
                "True Positives": rule_data["true_positives"],
                "False Positives": rule_data["false_positives"],
                "False Negatives": rule_data["false_negatives"],
                "Precision": (
                    f"{rule_data['precision'] * 100:.1f}%"
                ),
                "Recall": (
                    f"{rule_data['recall'] * 100:.1f}%"
                ),
                "F1-Score": (
                    f"{rule_data['f1_score'] * 100:.1f}%"
                ),
            }
        )

    if rule_rows:
        st.dataframe(
            pd.DataFrame(rule_rows),
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        f"Evaluated assets: {report['dataset_summary']['total_evaluated_assets']} | "
        f"Ground-truth anomalies: {report['dataset_summary']['ground_truth_anomalies']} | "
        f"Detected anomalies: {report['dataset_summary']['total_detected_anomalies']}"
    )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "Reverse Logistics & Asset Custody Tracking Platform | "
    "Streamlit Dashboard | Stage 9"
)
