# AI Usage and Prompt History

**Project:** Reverse Logistics & Asset Custody Control Tower  
**Purpose:** Transparent disclosure of AI assistance for the engineering candidate submission.

## 1. Summary

I used AI assistants as supporting pair-programming tools during development to explore architectural alternatives, review domain modeling approaches for reverse logistics, clarify mathematical formulas (such as great-circle distance for transit teleportation detection), assist in drafting test scaffolding, and troubleshoot local and cloud deployment configurations.

AI suggestions were treated as technical proposals to evaluate against the specific problem requirements, not as authoritative implementations. I remain entirely responsible for the code in this repository, the architectural design decisions, the database normalization, the integrity rules, the documentation, and all reported test and evaluation results.

---

## 2. Prompt History and Engineering Context

### 2.1 Reverse Logistics Domain and Custody Modeling

**Question 1 — Reconstructing asset custody without overwriting history**
> In a reverse logistics system for reusable containers and pallets, how should custody transfers be recorded so that we can always reconstruct the full historical audit trail and point-in-time custody without overwriting the current location column?

**Purpose:** Explore event-sourcing patterns versus mutable state columns for asset tracking across multi-facility reverse logistics loops.  
**Human Decision:** Adopted an append-only `custody_events` ledger. The current location and custodian of any asset are dynamically reconstructed by querying the most recent valid event in chronological order.

**Question 2 — Calculating outstanding days across returns**
> What is the standard operational formula for tracking outstanding days on return authorizations (RMAs), taking into account whether an asset has been physically received or is still pending intake?

**Purpose:** Ensure standard supply-chain return aging calculations.  
**Human Decision:** Implemented the deterministic formula:
$$\text{outstanding\_days} = \max(0, (\text{actual\_return\_date} \text{ or } \text{reference\_date}) - \text{expected\_return\_date})$$
Assets intaken on or before their expected return date have zero outstanding overdue days; pending returns calculate active delay against the operational reference date.

---

### 2.2 Anomaly Detection and Spatial Teleportation Rules

**Question 3 — Detecting impossible travel speeds between custody scans**
> How can we detect impossible physical movement ("teleportation" or multiple active locations) between two consecutive custody scans of the same reusable asset using GPS coordinates and timestamps?

**Purpose:** Explore great-circle spatial calculation for logistics anomaly detection.  
**Human Decision:** Implemented Haversine spherical distance calculation between sequential scan locations:
$$d = 2r \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$
If computed transit velocity $v = d / \Delta t$ exceeds 600 mph (commercial flight / ground transit threshold) between consecutive scans under 24 hours apart, the asset is quarantined under `MULTIPLE_ACTIVE_LOCATIONS`.

**Question 4 — Explainable operational exception rules**
> How should we structure anomaly detection rules so they produce explainable diagnostic records for warehouse operators rather than black-box scores?

**Purpose:** Ensure operational transparency for triage operators.  
**Human Decision:** Created 5 explicit, deterministic rule detectors (`MULTIPLE_ACTIVE_LOCATIONS`, `RETURN_BEFORE_DISPATCH`, `DUPLICATE_REFUND`, `REPAIR_WITHOUT_INSPECTION`, `MISSING_CUSTODY_ACTOR`). Each rule produces structured evidence including affected record ID, severity, root cause explanation, and recommended operator action.

---

### 2.3 Financial Reconciliation and Double-Entry Ledger

**Question 5 — Preventing duplicate deposit refunds**
> In reusable asset management with security deposits, what database constraints and business logic checks should be applied to prevent duplicate refunds or refunds exceeding the original deposit?

**Purpose:** Prevent financial discrepancies and deposit leakage in circular supply chains.  
**Human Decision:** Modeled the `deposit_ledger` as an immutable double-entry ledger. Implemented cumulative ledger validation where total refunded amounts for an asset cannot exceed the initial deposit charge, and refund transactions cannot precede diagnostic inspection.

---

### 2.4 User Interface and Operator Workflows

**Question 6 — Streamlit architecture for multi-workspace operations**
> How should a multi-view operations dashboard be structured in Streamlit so that operators can navigate between fleet metrics, GIS maps, return workflows, and exception resolution without reloading the entire database on every tab switch?

**Purpose:** Optimize Streamlit session state and caching for enterprise usability.  
**Human Decision:** Implemented a unified workspace selector in the sidebar routing to 6 focused views, utilizing `@st.cache_data` for static reference data and dynamic session queries for interactive operator actions (such as resolving operational exceptions).

---

### 2.5 Testing, Troubleshooting, and Deployment

**Question 7 — Port conflicts and Streamlit headless configuration**
> When running Streamlit on macOS in development, what causes browser launch failures or port conflicts when transitioning from local terminal to background daemons?

**Purpose:** Troubleshoot local development server startup and browser LaunchServices quirks.  
**Human Decision:** Configured `.streamlit/config.toml` with `headless = false`, `enableCORS = false`, and `enableXsrfProtection = false` for local interactive execution while maintaining fallback direct IPv4 binding (`127.0.0.1:8501`).

**Question 8 — Cloud deployment database bootstrapping**
> How can a Streamlit Cloud deployment automatically bootstrap its database on a fresh container launch without requiring manual terminal commands or committing binary SQLite files to Git?

**Purpose:** Guarantee zero-setup deployment for hackathon reviewers and judges.  
**Human Decision:** Implemented `ensure_database_ready()` in `src/dashboard/app.py`, which checks for the SQLite database upon app initialization, automatically generating the 500-asset starter dataset and ground truth within 2 seconds if not present.

---

## 3. Scope of AI Assistance vs. Human Ownership

| Functional Area | Where AI Assisted | Human Engineering Ownership |
|---|---|---|
| **Architecture & Schema** | Suggested entity relationships and cardinality naming. | Designed 10 normalized relational tables, foreign key constraints, and immutable audit logs. |
| **Domain Services** | Proposed Haversine formula and composite grading formula. | Implemented lifecycle state machine, validation engine (12 checks), and exception resolution workflow. |
| **API Layer** | Drafted initial Pydantic schema templates. | Configured FastAPI routing, query filters, pagination, and OpenAPI metadata. |
| **Presentation Tier** | Provided CSS layout recommendations for dark/light contrast. | Built custom Navy/Teal enterprise SaaS theme, Folium GIS map integration, and operator resolution forms. |
| **Testing & Quality** | Generated initial parameterized test scaffolding. | Authored all 20 Pytest unit/integration tests and verified 100% precision/recall benchmarks. |
| **Deployment** | Reviewed Dockerfile and Procfile syntax. | Configured Streamlit Cloud settings, auto-bootstrap routines, and repository documentation. |

---

## 4. Limitations and Responsible Engineering Disclosures

1. **Synthetic Data Context:** All evaluation metrics are calculated against synthetic anomalies deliberately injected into generated records with seed `20261022`. They demonstrate that the business logic and detection rules function correctly according to specification, but do not represent performance on noisy real-world warehouse telemetry.
2. **Deterministic Thresholds:** Physical parameters (such as the 600 mph speed threshold) are rule-based heuristics designed for operational triage. In a live production environment, these would be calibrated against carrier GPS feeds and route schedules.
3. **Demo Authentication:** The dashboard currently operates in open evaluation mode for hackathon review. Production deployment would require enterprise Single Sign-On (SSO) via OAuth2/OIDC.
4. **Persistence Tier:** The project utilizes SQLite in WAL mode for lightweight, zero-dependency local evaluation. For high-concurrency production deployments, the SQLAlchemy model layer is designed to target PostgreSQL without schema modifications.

---

## 5. Verification Statement

I confirm that:
- All reported test results (`20 passed in 0.97s`) reflect actual automated test runs executed in the project virtual environment.
- No test outputs, metrics, or evaluation numbers have been fabricated or hard-coded.
- All code in this repository has been reviewed, tested, and validated in both local and cloud deployment environments.
