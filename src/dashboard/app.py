"""
RELOOP 360 – Intelligent Reverse Logistics & Reusable Asset Management Platform.
Tagline: Track. Recover. Reuse. Reconcile.
Three-Tier Presentation Layer: Modern Enterprise SaaS Dashboard.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
from datetime import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import func

from src.dashboard.theme import inject_theme
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
from src.services.validation_engine import ValidationEngine
from src.services.lifecycle_engine import LifecycleEngine

# --------------------------------------------------
# PAGE CONFIGURATION & BRANDING
# --------------------------------------------------

st.set_page_config(
    page_title="ReLoop 360 | Reverse Logistics Intelligence",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

st.title("🔄 RELOOP 360")
st.caption("**Track. Recover. Reuse. Reconcile.** | Enterprise Reverse Logistics & Asset Management Intelligence")

# --------------------------------------------------
# SIDEBAR NAVIGATION & FILTERS
# --------------------------------------------------

st.sidebar.markdown("## 🔄 **RELOOP 360**")
st.sidebar.caption("Reverse Logistics Intelligence Platform")

view = st.sidebar.radio(
    "Control Tower Navigation",
    [
        "Executive Control Tower",
        "Asset Tracking & Custody Explorer",
        "Return & Repair Management",
        "Exception Management Hub",
        "Data Quality & Model Scorecard",
        "Reports & Data Exports",
    ],
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎛️ Global Data Filters")

db = SessionLocal()
try:
    all_owners = ["All"] + [o.owner_name for o in db.query(Owner).all()]
    all_types = ["All"] + [t.type_name for t in db.query(AssetType).all()]
    all_locations = ["All"] + [loc.location_name for loc in db.query(Location).all()]
    all_statuses = ["All", "available", "in_transit", "in_use", "under_repair", "lost", "retired"]
finally:
    db.close()

selected_owner = st.sidebar.selectbox("Owner", all_owners, index=0)
selected_type = st.sidebar.selectbox("Asset Category", all_types, index=0)
selected_status = st.sidebar.selectbox("Lifecycle Status", all_statuses, index=0)

st.sidebar.markdown("---")
st.sidebar.success("System Status: **ONLINE**")
st.sidebar.info("Database: **SQLite (WAL Mode)**\nArchitecture: **Three-Tier Modular**")


# ==============================================================================
# VIEW 1: EXECUTIVE CONTROL TOWER
# ==============================================================================

if view == "Executive Control Tower":

    st.header("📊 Executive Fleet & Operations Control Tower")
    st.write(
        "Real-time command center coordinating return merchandise, reusable packaging, "
        "pallets, containers, and custody transitions across all facilities."
    )

    db = SessionLocal()
    try:
        # Build filtered query for assets
        asset_q = db.query(ReusableAsset)
        if selected_owner != "All":
            asset_q = asset_q.join(Owner).filter(Owner.owner_name == selected_owner)
        if selected_type != "All":
            asset_q = asset_q.join(AssetType).filter(AssetType.type_name == selected_type)
        if selected_status != "All":
            asset_q = asset_q.filter(ReusableAsset.lifecycle_status == selected_status)

        filtered_asset_ids = [a.asset_id for a in asset_q.all()]

        # 10 Required KPI metrics
        total_assets = len(filtered_asset_ids) if (selected_owner != "All" or selected_type != "All" or selected_status != "All") else db.query(ReusableAsset).count()
        total_shipments = db.query(Shipment).count()
        in_circulation = db.query(ReusableAsset).filter(ReusableAsset.lifecycle_status.in_(["in_transit", "in_use"])).count()
        returned_assets = db.query(ReusableAsset).filter(ReusableAsset.lifecycle_status.in_(["available", "under_repair"])).count()
        lost_assets = db.query(ReusableAsset).filter(ReusableAsset.lifecycle_status == "lost").count()
        damaged_assets = db.query(ReusableAsset).filter(ReusableAsset.lifecycle_status == "under_repair").count()

        total_rmas = db.query(ReturnAuthorization).count()
        overdue_assets = db.query(ReturnAuthorization).filter(ReturnAuthorization.return_status == "requested").count()

        total_charges = db.query(func.sum(DepositLedger.amount)).filter(DepositLedger.transaction_type == "charge").scalar() or 0
        total_refunds = db.query(func.sum(DepositLedger.amount)).filter(DepositLedger.transaction_type == "refund").scalar() or 0
        total_deposit_balance = max(0.0, float(total_charges) - float(total_refunds))

        anomalies = AnomalyDetector.scan_all(db, sync_exceptions_table=False)
        total_exceptions = len(anomalies)

        recovery_rate = round(((returned_assets) / total_assets) * 100, 1) if total_assets > 0 else 0.0

        # Status distribution
        status_counts = (
            db.query(ReusableAsset.lifecycle_status, func.count(ReusableAsset.asset_id))
            .group_by(ReusableAsset.lifecycle_status)
            .all()
        )
        status_df = pd.DataFrame(status_counts, columns=["Lifecycle Status", "Units"])

        # Category distribution
        cat_counts = (
            db.query(AssetType.type_name, func.count(ReusableAsset.asset_id))
            .join(ReusableAsset, ReusableAsset.asset_type_id == AssetType.asset_type_id)
            .group_by(AssetType.type_name)
            .all()
        )
        cat_df = pd.DataFrame(cat_counts, columns=["Asset Category", "Units"])

        # Shipment status distribution
        ship_counts = (
            db.query(Shipment.shipment_status, func.count(Shipment.shipment_id))
            .group_by(Shipment.shipment_status)
            .all()
        )
        ship_df = pd.DataFrame(ship_counts, columns=["Shipment Status", "Shipments"])

        # Inspections condition breakdown
        cond_counts = (
            db.query(Inspection.condition_status, func.count(Inspection.inspection_id))
            .group_by(Inspection.condition_status)
            .all()
        )
        cond_df = pd.DataFrame(cond_counts, columns=["Condition", "Units"])

        # Exceptions by Issue Type
        anom_type_counts = {}
        for a in anomalies:
            t = a.get("issue_type", "OTHER")
            anom_type_counts[t] = anom_type_counts.get(t, 0) + 1
        anom_type_df = pd.DataFrame(list(anom_type_counts.items()), columns=["Issue Type", "Exceptions"])

    finally:
        db.close()

    # Render 10 KPI Cards in two clean rows of 5
    st.subheader("📌 Key Performance Indicators (Real-time Calculated)")

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("1. Total Assets", f"{total_assets:,}")
    k2.metric("2. Total Shipments", f"{total_shipments:,}")
    k3.metric("3. In Circulation", f"{in_circulation:,}")
    k4.metric("4. Assets Returned", f"{returned_assets:,}")
    k5.metric("5. Overdue Assets", f"{overdue_assets:,}")

    k6, k7, k8, k9, k10 = st.columns(5)
    k6.metric("6. Lost Assets", f"{lost_assets:,}")
    k7.metric("7. Damaged Units", f"{damaged_assets:,}")
    k8.metric("8. Deposit Balance", f"₹{total_deposit_balance:,.2f}")
    k9.metric("9. Total Exceptions", f"{total_exceptions:,}")
    k10.metric("10. Recovery Rate", f"{recovery_rate:.1f}%")

    st.markdown("---")

    # Visualizations Row 1
    r1_col1, r1_col2 = st.columns(2)
    with r1_col1:
        st.markdown("#### 🔄 Asset Lifecycle Distribution")
        st.bar_chart(status_df.set_index("Lifecycle Status"))
    with r1_col2:
        st.markdown("#### 📦 Inventory by Product Category")
        st.bar_chart(cat_df.set_index("Asset Category"))

    # Visualizations Row 2
    r2_col1, r2_col2 = st.columns(2)
    with r2_col1:
        st.markdown("#### 🚚 Shipment Status Distribution")
        st.bar_chart(ship_df.set_index("Shipment Status"))
    with r2_col2:
        st.markdown("#### 🛠️ Quality & Condition (Damaged vs. Good)")
        st.bar_chart(cond_df.set_index("Condition"))

    # Visualizations Row 3
    r3_col1, r3_col2 = st.columns(2)
    with r3_col1:
        st.markdown("#### 💰 Deposit Reconciliation Overview")
        fin_df = pd.DataFrame({
            "Category": ["Total Charges", "Total Refunds", "Net Balance"],
            "Amount (₹)": [float(total_charges), float(total_refunds), total_deposit_balance]
        })
        st.bar_chart(fin_df.set_index("Category"))
    with r3_col2:
        st.markdown("#### 🚨 Exception Distribution by Issue Type")
        if not anom_type_df.empty:
            st.bar_chart(anom_type_df.set_index("Issue Type"))
        else:
            st.info("No exceptions detected.")


# ==============================================================================
# VIEW 2: ASSET TRAJECTORY & CUSTODY EXPLORER
# ==============================================================================

elif view == "Asset Tracking & Custody Explorer":

    st.header("🛰️ Asset Trajectory & Custody Reconstruction")
    st.write(
        "Inspect point-in-time custody handoffs, reconstructed physical location, "
        "current custodian, and interactive GIS transit scans."
    )

    db = SessionLocal()
    try:
        asset_records = db.query(ReusableAsset.asset_id, ReusableAsset.asset_code).order_by(ReusableAsset.asset_id).all()
        locations = db.query(Location).all()
        location_lookup = {loc.location_name: loc for loc in locations}
    finally:
        db.close()

    if not asset_records:
        st.warning("No assets available.")
    else:
        options = {f"{a.asset_code} (ID: {a.asset_id})": a.asset_id for a in asset_records}
        selected_label = st.selectbox("Select Asset to Reconstruct:", list(options.keys()))
        selected_id = options[selected_label]

        db = SessionLocal()
        try:
            recon = CustodyService.get_asset_trajectory(db, selected_id)
            asset = db.query(ReusableAsset).filter(ReusableAsset.asset_id == selected_id).first()
            asset_type = db.query(AssetType).filter(AssetType.asset_type_id == asset.asset_type_id).first() if asset else None
        finally:
            db.close()

        if recon:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Asset Code", recon["asset_code"])
            m2.metric("Category", asset_type.type_name if asset_type else "N/A")
            m3.metric("Lifecycle Status", recon["lifecycle_status"].upper())
            m4.metric("Custody Hops", recon["total_events"])

            st.info(f"**Current Reconstructed Location:** {recon['current_location_description']}")
            st.write(f"**Current Legal Custodian:** `{recon['current_custodian']}` | **Last Scan Timestamp:** `{recon['last_event_time'] or 'N/A'}`")

            st.markdown("---")
            st.markdown("#### 📜 Chronological Immutable Chain of Custody")

            if recon["trajectory"]:
                traj_df = pd.DataFrame(recon["trajectory"])
                st.dataframe(traj_df, use_container_width=True, hide_index=True)

                # Geospatial map
                city_coordinates = {
                    "Hyderabad": (17.3850, 78.4867),
                    "Bengaluru": (12.9716, 77.5946),
                    "Mumbai": (19.0760, 72.8777),
                    "Chennai": (13.0827, 80.2707),
                }

                points = []
                for step in recon["trajectory"]:
                    loc_name = step.get("to_location")
                    loc = location_lookup.get(loc_name)
                    if loc and loc.city in city_coordinates:
                        coords = city_coordinates[loc.city]
                        points.append({"lat": coords[0], "lon": coords[1], "Location": loc.city})

                if points:
                    st.markdown("#### 🗺️ Geospatial Transit Scan Route")
                    st.map(pd.DataFrame(points), zoom=4)
            else:
                st.warning("No custody events recorded for this asset.")


# ==============================================================================
# VIEW 3: RETURN & REPAIR MANAGEMENT
# ==============================================================================

elif view == "Return & Repair Management":

    st.header("🔄 Return Authorizations, Triage & Repair Ledger")
    st.write(
        "Manage end-to-end reverse logistics: return merchandise authorizations (RMAs), "
        "intake diagnostic inspections (Grades A/B/C/F), repair triage, and deposit settlements."
    )

    db = SessionLocal()
    try:
        rmas = db.query(ReturnAuthorization).order_by(ReturnAuthorization.request_date.desc()).all()
        inspections = db.query(Inspection).all()
        repairs = db.query(Repair).all()
        ledgers = db.query(DepositLedger).all()

        total_rep_cost = sum(float(r.repair_cost) for r in repairs)
        total_refunds = sum(float(l.amount) for l in ledgers if l.transaction_type == "refund")
    finally:
        db.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total RMAs", len(rmas))
    c2.metric("Intake Inspections", len(inspections))
    c3.metric("Refurbishments", len(repairs))
    c4.metric("Repair Expenses", f"₹{total_rep_cost:,.2f}")

    st.markdown("---")

    t1, t2, t3 = st.tabs(["Return Authorizations (RMA)", "Diagnostic Inspections", "Repair Records"])

    with t1:
        st.markdown("#### Active Return Authorizations (RMAs)")
        rma_data = []
        now = datetime(2026, 10, 22)
        for r in rmas:
            # Calculate outstanding days formula: max(0, reference_date - expected_return_date)
            exp_date = r.request_date + pd.Timedelta(days=14)
            days_out = LifecycleEngine.calculate_days_outstanding(now, exp_date)
            rma_data.append({
                "RMA Code": r.return_code,
                "Asset ID": r.asset_id,
                "Requested By": r.requested_by,
                "Request Date": r.request_date.strftime("%Y-%m-%d"),
                "Expected Return": exp_date.strftime("%Y-%m-%d"),
                "Days Outstanding": days_out,
                "Status": r.return_status.upper(),
            })
        st.dataframe(pd.DataFrame(rma_data), use_container_width=True, hide_index=True)

    with t2:
        st.markdown("#### Hardware Diagnostic Inspections & Grading")
        insp_data = []
        for i in inspections:
            insp_data.append({
                "Inspection ID": i.inspection_id,
                "Asset ID": i.asset_id,
                "Inspector": i.inspector_name,
                "Condition": i.condition_status.upper(),
                "Inspection Date": i.inspection_date.strftime("%Y-%m-%d"),
                "Diagnostic Remarks": i.remarks or "N/A",
            })
        st.dataframe(pd.DataFrame(insp_data), use_container_width=True, hide_index=True)

    with t3:
        st.markdown("#### Refurbishment & Repair Financial Ledger")
        rep_data = []
        for rep in repairs:
            rep_data.append({
                "Repair ID": f"REP-2026-{rep.repair_id:06d}",
                "Asset ID": rep.asset_id,
                "Inspection ID": rep.inspection_id,
                "Description": rep.repair_description,
                "Cost (₹)": float(rep.repair_cost),
                "Status": rep.repair_status.upper(),
                "Opened Date": rep.opened_at.strftime("%Y-%m-%d"),
                "Closed Date": rep.closed_at.strftime("%Y-%m-%d") if rep.closed_at else "IN PROGRESS",
            })
        st.dataframe(pd.DataFrame(rep_data), use_container_width=True, hide_index=True)


# ==============================================================================
# VIEW 4: EXCEPTION MANAGEMENT HUB (SECTION 12)
# ==============================================================================

elif view == "Exception Management Hub":

    st.header("🚨 Exception Management & Resolution Hub")
    st.write(
        "Detects and manages the **5 Mandatory Reverse Logistics Edge Cases**. "
        "Allows authorized operators to audit anomalies, mark records under review, "
        "and record resolution notes without deleting historical anomaly logs."
    )

    db = SessionLocal()
    try:
        anomalies = AnomalyDetector.scan_all(db, sync_exceptions_table=True)
    finally:
        db.close()

    crit_cnt = sum(1 for a in anomalies if a.get("severity") == "CRITICAL")
    high_cnt = sum(1 for a in anomalies if a.get("severity") == "HIGH")
    open_cnt = sum(1 for a in anomalies if a.get("resolution_status") == "Open")
    res_cnt = sum(1 for a in anomalies if a.get("resolution_status") == "Resolved")

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Total Exceptions", len(anomalies))
    e2.metric("Critical Invariants", crit_cnt)
    e3.metric("Status: Open", open_cnt)
    e4.metric("Status: Resolved", res_cnt)

    st.markdown("---")

    # Exception Table
    if anomalies:
        exc_df = pd.DataFrame(anomalies)[[
            "exception_id", "issue_type", "affected_entity", "affected_record_id",
            "severity", "detection_result", "resolution_status", "resolution_notes"
        ]].rename(columns={
            "exception_id": "Exception ID",
            "issue_type": "Issue Type",
            "affected_entity": "Entity",
            "affected_record_id": "Record ID",
            "severity": "Severity",
            "detection_result": "Detection",
            "resolution_status": "Status",
            "resolution_notes": "Resolution Notes",
        })

        st.dataframe(exc_df, use_container_width=True, hide_index=True)

        st.markdown("### ✍️ Operator Action: Review & Resolve Exception")
        with st.form("resolve_exception_form"):
            exc_ids = [a["exception_id"] for a in anomalies]
            chosen_exc = st.selectbox("Select Exception to Update:", exc_ids)
            chosen_status = st.selectbox("Update Resolution Status:", ["Under Review", "Resolved", "Open"])
            chosen_notes = st.text_input("Enter Resolution Notes:", "Verified with warehouse dock agent. Flagged asset quarantined.")
            submitted = st.form_submit_button("Update Exception Record", type="primary")

            if submitted:
                db_action = SessionLocal()
                try:
                    ok = AnomalyDetector.resolve_exception(db_action, chosen_exc, chosen_status, chosen_notes)
                    if ok:
                        st.success(f"Exception {chosen_exc} updated to '{chosen_status}' successfully!")
                        st.rerun()
                    else:
                        st.error(f"Failed to update exception {chosen_exc}.")
                finally:
                    db_action.close()

        with st.expander("🔍 Read Detailed Anomaly Root-Cause Analysis"):
            for idx, a in enumerate(anomalies, 1):
                st.markdown(f"**{idx}. [{a['exception_id']}] {a['issue_type']} — Severity: `{a['severity']}`**")
                st.caption(f"Entity: {a['affected_entity']} | Record: {a['affected_record_id']} | Status: {a['resolution_status']}")
                st.write(a["details"])
                st.markdown("---")


# ==============================================================================
# VIEW 5: DATA QUALITY & MODEL SCORECARD
# ==============================================================================

elif view == "Data Quality & Model Scorecard":

    st.header("🎯 Data Quality & Ground-Truth Model Evaluation")
    st.write(
        "Empirical benchmarks comparing automated anomaly detector output against "
        "the authoritative ground-truth dataset (`data/processed/ground_truth.json`)."
    )

    db = SessionLocal()
    try:
        report = EvaluationEngine.evaluate(db)
        val_report = ValidationEngine.run_all_checks(db)
    finally:
        db.close()

    m = report["aggregate_metrics"]
    cm = report["confusion_matrix"]

    st.subheader("Automated Data Quality Audit (12 Automated Checks)")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Data Quality Score", f"{val_report['data_quality_percentage']:.1f}%")
    q2.metric("Passed Checks", f"{val_report['passed_checks']}/{val_report['total_checks']}")
    q3.metric("Failed Checks", val_report["failed_checks"])
    q4.metric("Acceptance Criteria", "PASSED" if val_report["acceptance_criteria_satisfied"] else "FAILED")

    val_df = pd.DataFrame(val_report["checks"])[["check_id", "name", "category", "status", "details"]].rename(columns={
        "check_id": "Check #",
        "name": "Audit Name",
        "category": "Domain",
        "status": "Result",
        "details": "Audit Evidence",
    })
    st.dataframe(val_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Model Performance Benchmark vs. Ground Truth")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Accuracy", f"{m['accuracy'] * 100:.1f}%")
    c2.metric("Precision", f"{m['precision'] * 100:.1f}%")
    c3.metric("Recall", f"{m['recall'] * 100:.1f}%")
    c4.metric("F1-Score", f"{m['f1_score'] * 100:.1f}%")
    c5.metric("Specificity", f"{m['specificity'] * 100:.1f}%")

    st.markdown("#### Confusion Matrix")
    cm_df = pd.DataFrame(
        [
            [cm["true_positives"], cm["false_negatives"]],
            [cm["false_positives"], cm["true_negatives"]]
        ],
        index=["Actual Anomaly", "Actual Clean"],
        columns=["Predicted Anomaly", "Predicted Clean"]
    )
    st.table(cm_df)

    st.markdown("#### Per-Rule Breakdown")
    rule_table = []
    for r_code, data in report["rule_breakdown"].items():
        rule_table.append({
            "Rule Code": r_code,
            "True Positives": data["true_positives"],
            "False Positives": data["false_positives"],
            "False Negatives": data["false_negatives"],
            "Precision": f"{data['precision']*100:.1f}%",
            "Recall": f"{data['recall']*100:.1f}%",
            "F1-Score": f"{data['f1_score']*100:.1f}%"
        })
    st.dataframe(pd.DataFrame(rule_table), use_container_width=True, hide_index=True)


# ==============================================================================
# VIEW 6: REPORTS & DATA EXPORTS (SECTION 17)
# ==============================================================================

elif view == "Reports & Data Exports":

    st.header("📥 Reports, Provenance & Data Exports")
    st.write(
        "Export complete operational datasets in CSV or JSON formats. "
        "Generated using fixed seed `20261022` with complete synthetic provenance."
    )

    db = SessionLocal()
    try:
        # Load tables into DataFrames for instant export
        assets_export = pd.read_sql("SELECT * FROM reusable_assets", db.bind)
        shipments_export = pd.read_sql("SELECT * FROM shipments", db.bind)
        custody_export = pd.read_sql("SELECT * FROM custody_events", db.bind)
        rma_export = pd.read_sql("SELECT * FROM return_authorizations", db.bind)
        insp_export = pd.read_sql("SELECT * FROM inspections", db.bind)
        rep_export = pd.read_sql("SELECT * FROM repairs", db.bind)
        ledger_export = pd.read_sql("SELECT * FROM deposit_ledger", db.bind)
    finally:
        db.close()

    st.markdown("### 📊 One-Click Entity Exports")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button("📥 Export Assets (CSV)", assets_export.to_csv(index=False), "assets.csv", "text/csv")
        st.download_button("📥 Export RMAs (CSV)", rma_export.to_csv(index=False), "return_authorizations.csv", "text/csv")
    with col2:
        st.download_button("📥 Export Shipments (CSV)", shipments_export.to_csv(index=False), "shipments.csv", "text/csv")
        st.download_button("📥 Export Inspections (CSV)", insp_export.to_csv(index=False), "inspections.csv", "text/csv")
    with col3:
        st.download_button("📥 Export Custody Events (CSV)", custody_export.to_csv(index=False), "custody_events.csv", "text/csv")
        st.download_button("📥 Export Deposit Ledger (CSV)", ledger_export.to_csv(index=False), "deposit_ledger.csv", "text/csv")

    st.markdown("---")
    st.markdown("### 📑 Evaluation & Ground Truth Benchmark Exports")

    gt_csv_path = Path(PROJECT_ROOT) / "data" / "processed" / "ground_truth.csv"
    val_json_path = Path(PROJECT_ROOT) / "data" / "processed" / "validation_report.json"

    b1, b2 = st.columns(2)
    with b1:
        if gt_csv_path.exists():
            st.download_button("📥 Download Ground Truth Benchmark (CSV)", gt_csv_path.read_text(), "ground_truth.csv", "text/csv")
    with b2:
        if val_json_path.exists():
            st.download_button("📥 Download Validation Report (JSON)", val_json_path.read_text(), "validation_report.json", "application/json")


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.markdown("---")
st.caption(
    "**RELOOP 360** · Enterprise Reverse Logistics & Reusable Asset Management Intelligence · "
    "Designed for Hackathon Excellence · Python 3.11 · SQLite · FastAPI · Streamlit"
)
