
# Data Dictionary
## Reverse Logistics & Asset Custody Tracking System

## 1. Overview

This document defines the database entities, attributes, relationships, constraints, and business rules for the Reverse Logistics & Asset Custody Tracking System.

The system tracks reusable packaging and logistics assets as they move between suppliers, carriers, warehouses, and other operational locations.

## 2. Core Entities

### 2.1 Owners

Stores organizations that own or are responsible for reusable assets.

| Column | Data Type | Constraints | Description |
|---|---|---|---|
| owner_id | Integer | Primary Key | Unique owner identifier |
| owner_name | String(150) | Not Null, Unique | Organization name |
| owner_type | String(30) | Not Null | Supplier, customer, or internal |
| contact_email | String(150) | Nullable | Contact email |
| is_active | Boolean | Default True | Whether the owner is active |

### 2.2 Locations

Stores suppliers, warehouses, distribution centers, and other asset locations.

| Column | Data Type | Constraints | Description |
|---|---|---|---|
| location_id | Integer | Primary Key | Unique location identifier |
| location_name | String(150) | Not Null | Location name |
| location_type | String(30) | Not Null | Supplier, warehouse, distribution center, or customer |
| city | String(100) | Not Null | City |
| state | String(100) | Not Null | State |
| country | String(100) | Not Null | Country |
| is_active | Boolean | Default True | Whether the location is active |

### 2.3 Asset Types

Defines categories of reusable logistics assets and their lifecycle rules.

| Column | Data Type | Constraints | Description |
|---|---|---|---|
| asset_type_id | Integer | Primary Key | Unique asset type identifier |
| type_name | String(100) | Not Null, Unique | Pallet, crate, container, reusable box, or equipment |
| description | Text | Nullable | Asset type description |
| expected_return_days | Integer | Not Null | Expected return period |
| deposit_amount | Numeric(12,2) | Not Null | Standard refundable deposit |
| is_active | Boolean | Default True | Whether the asset type is active |

### 2.4 Reusable Assets

Stores individual reusable assets tracked by the system.

| Column | Data Type | Constraints | Description |
|---|---|---|---|
| asset_id | Integer | Primary Key | Internal asset identifier |
| asset_code | String(50) | Not Null, Unique | Unique physical asset code |
| asset_type_id | Integer | Foreign Key | References Asset Types |
| owner_id | Integer | Foreign Key | References Owners |
| serial_number | String(100) | Nullable | Manufacturer serial number |
| manufacture_date | Date | Nullable | Manufacturing date |
| lifecycle_status | String(30) | Not Null | Available, in_transit, in_use, under_repair, lost, or retired |
| created_at | DateTime | Not Null | Asset registration timestamp |

### 2.5 Shipments

Stores shipment records used to move reusable assets between locations.

| Column | Data Type | Constraints | Description |
|---|---|---|---|
| shipment_id | Integer | Primary Key | Unique shipment identifier |
| shipment_code | String(50) | Not Null, Unique | Shipment reference |
| origin_location_id | Integer | Foreign Key | References Locations |
| destination_location_id | Integer | Foreign Key | References Locations |
| carrier_name | String(150) | Not Null | Carrier organization |
| dispatch_date | DateTime | Not Null | Shipment dispatch timestamp |
| expected_delivery_date | DateTime | Nullable | Expected delivery timestamp |
| actual_delivery_date | DateTime | Nullable | Actual delivery timestamp |
| shipment_status | String(30) | Not Null | Planned, dispatched, delivered, or cancelled |

### 2.6 Custody Events

Maintains the append-only history of asset movements and custody changes.

| Column | Data Type | Constraints | Description |
|---|---|---|---|
| event_id | Integer | Primary Key | Unique event identifier |
| asset_id | Integer | Foreign Key | References Reusable Assets |
| shipment_id | Integer | Foreign Key, Nullable | Related shipment |
| from_location_id | Integer | Foreign Key, Nullable | Previous location |
| to_location_id | Integer | Foreign Key | New location |
| actor_name | String(150) | Not Null | Person or system recording the event |
| event_type | String(30) | Not Null | Dispatch, transfer, receipt, or return |
| event_timestamp | DateTime | Not Null | Time the event occurred |
| notes | Text | Nullable | Additional event information |

### 2.7 Return Authorizations

Stores requests and approvals for returning reusable assets.

| Column | Data Type | Constraints | Description |
|---|---|---|---|
| return_id | Integer | Primary Key | Unique return authorization identifier |
| return_code | String(50) | Not Null, Unique | Return reference |
| asset_id | Integer | Foreign Key | References Reusable Assets |
| shipment_id | Integer | Foreign Key, Nullable | Related return shipment |
| requested_by | String(150) | Not Null | Person or organization requesting return |
| request_date | DateTime | Not Null | Request timestamp |
| approved_date | DateTime | Nullable | Approval timestamp |
| return_status | String(30) | Not Null | Requested, approved, received, rejected, or cancelled |

### 2.8 Inspections

Stores condition checks performed when assets are returned or received.

| Column | Data Type | Constraints | Description |
|---|---|---|---|
| inspection_id | Integer | Primary Key | Unique inspection identifier |
| asset_id | Integer | Foreign Key | References Reusable Assets |
| return_id | Integer | Foreign Key, Nullable | Related return authorization |
| inspector_name | String(150) | Not Null | Person performing inspection |
| inspection_date | DateTime | Not Null | Inspection timestamp |
| condition_status | String(30) | Not Null | Good, damaged, or unusable |
| remarks | Text | Nullable | Inspection findings |

### 2.9 Repairs

Tracks maintenance and repair work performed on reusable assets.

| Column | Data Type | Constraints | Description |
|---|---|---|---|
| repair_id | Integer | Primary Key | Unique repair identifier |
| asset_id | Integer | Foreign Key | References Reusable Assets |
| inspection_id | Integer | Foreign Key | References Inspections |
| repair_description | Text | Not Null | Description of repair work |
| repair_cost | Numeric(12,2) | Not Null | Repair cost |
| repair_status | String(30) | Not Null | Open, in_progress, or completed |
| opened_at | DateTime | Not Null | Repair start timestamp |
| closed_at | DateTime | Nullable | Repair completion timestamp |

### 2.10 Deposit Ledger

Records deposit charges, refunds, and adjustments for reusable assets.

| Column | Data Type | Constraints | Description |
|---|---|---|---|
| ledger_id | Integer | Primary Key | Unique ledger entry identifier |
| asset_id | Integer | Foreign Key | References Reusable Assets |
| shipment_id | Integer | Foreign Key, Nullable | Related shipment |
| transaction_type | String(30) | Not Null | Charge, refund, or adjustment |
| amount | Numeric(12,2) | Not Null | Transaction amount |
| transaction_date | DateTime | Not Null | Transaction timestamp |
| reference_code | String(100) | Not Null, Unique | Transaction reference |
| notes | Text | Nullable | Transaction explanation |

## 3. Entity Relationships

- One Owner can own multiple Reusable Assets.
- One Asset Type can classify multiple Reusable Assets.
- One Location can be the origin or destination of multiple Shipments.
- One Reusable Asset can have multiple Custody Events.
- One Shipment can be associated with multiple Custody Events.
- One Reusable Asset can have multiple Return Authorizations.
- One Return Authorization can have multiple Inspections.
- One Reusable Asset can have multiple Inspections and Repairs.
- One Inspection can be associated with multiple Repairs.
- One Reusable Asset can have multiple Deposit Ledger entries.

## 4. Important Business Rules

1. Every reusable asset must have a unique asset code.
2. Every asset must reference a valid asset type and owner.
3. Every shipment must have valid origin and destination locations.
4. Origin and destination locations must be different.
5. Custody events must preserve the complete movement history.
6. Existing custody events must never be overwritten to represent a new movement.
7. The current asset location must be reconstructed from valid custody events.
8. An asset cannot be received before it has been dispatched.
9. An asset cannot have two simultaneous current locations.
10. A return must not be processed before the corresponding dispatch.
11. A completed repair must reference a valid inspection.
12. A deposit refund must not exceed the eligible refundable balance.
13. The same deposit transaction must not be refunded twice.
14. Every custody event must identify the actor responsible for recording it.
15. Asset lifecycle transitions must follow permitted status changes.
16. All timestamps must be valid and chronologically consistent.

## 5. Exception Detection Requirements

The system must identify at least these five operational exceptions:

| Exception ID | Exception | Expected Detection |
|---|---|---|
| EX001 | Simultaneous asset locations | Detect conflicting custody records |
| EX002 | Return before dispatch | Detect invalid event chronology |
| EX003 | Duplicate deposit refund | Detect repeated refund transactions |
| EX004 | Repair completed without inspection | Detect missing inspection reference |
| EX005 | Custody event without actor | Detect missing actor information |

## 6. Data Integrity and Validation

- Primary keys must uniquely identify every record.
- Foreign keys must reference existing records.
- Required fields must not contain NULL values.
- Unique identifiers must not be duplicated.
- Monetary values must use fixed-precision numeric types.
- Dates and timestamps must follow valid chronological order.
- Enumerated status values must be validated.
- Database transactions must protect financial operations.
- Custody history must remain append-only.

## 7. Data Generation and Evaluation

Synthetic data will be generated using a fixed random seed of `20261022`.

Target full dataset:

| Entity | Target Records |
|---|---:|
| Reusable Assets | 20,000 |
| Shipments | 10,000 |
| Custody Events | 100,000 |

Normal baseline records must remain valid. Deliberately injected anomalies must be separately labelled in ground-truth data and must not be included as detector input labels.

Evaluation will measure:

- Primary and foreign key validity.
- Lifecycle rule compliance.
- Current-location reconstruction accuracy.
- Deposit reconciliation accuracy.
- Exception detection precision and recall.
- False-positive and false-negative rates.
- Reproducibility.
- Processing time.
