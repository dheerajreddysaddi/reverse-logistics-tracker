# Relational Schema, Keys and Cardinalities

## Foreign Keys & Relational Constraints

All foreign keys are strictly enforced by the relational engine (SQLite runs with `PRAGMA foreign_keys = ON;`).

| Child Column | Parent Column | On Delete / Constraint | Business Meaning |
|---|---|---|---|
| `reusable_assets.asset_type_id` | `asset_types.asset_type_id` | RESTRICT | An asset must belong to a registered asset category |
| `reusable_assets.owner_id` | `owners.owner_id` | RESTRICT | An asset must have an assigned owner organization |
| `shipments.origin_location_id` | `locations.location_id` | RESTRICT | Shipment origin must be an existing location |
| `shipments.destination_location_id` | `locations.location_id` | RESTRICT | Shipment destination must be an existing location |
| `custody_events.asset_id` | `reusable_assets.asset_id` | CASCADE | Events belong immutably to a specific asset |
| `custody_events.to_location_id` | `locations.location_id` | RESTRICT | Transfer destination must be a valid facility |
| `custody_events.from_location_id` | `locations.location_id` | SET NULL | Optional previous facility |
| `custody_events.shipment_id` | `shipments.shipment_id` | SET NULL | Optional associated shipment transit |
| `return_authorizations.asset_id` | `reusable_assets.asset_id` | RESTRICT | Return authorization must reference a valid asset |
| `return_authorizations.shipment_id` | `shipments.shipment_id` | SET NULL | Optional original outbound shipment |
| `inspections.asset_id` | `reusable_assets.asset_id` | RESTRICT | Inspection assessment assesses a specific asset |
| `inspections.return_id` | `return_authorizations.return_id` | SET NULL | Diagnostic triage for an RMA intake |
| `repairs.asset_id` | `reusable_assets.asset_id` | RESTRICT | Repair work order tracks physical asset |
| `repairs.inspection_id` | `inspections.inspection_id` | RESTRICT | Repairs must be justified by an inspection |
| `deposit_ledger.asset_id` | `reusable_assets.asset_id` | RESTRICT | Ledger transaction balances asset account |
| `deposit_ledger.shipment_id` | `shipments.shipment_id` | SET NULL | Optional shipment associated with deposit |

---

## Cardinalities

| Entity Relationship | Cardinality | Mandatory? | Notes & Integrity Checks |
|---|---|---|---|
| **Owner – ReusableAsset** | 1:N | Mandatory | An owner holds multiple assets; asset must have an owner |
| **AssetType – ReusableAsset** | 1:N | Mandatory | Reusable assets inherit return threshold and base deposit |
| **Location – Shipment** | 1:N | Mandatory | Origin and destination locations cannot be identical |
| **ReusableAsset – CustodyEvent** | 1:N | Mandatory | Append-only event history; current location derived from latest event |
| **Shipment – CustodyEvent** | 1:N | Optional | Transit events link to active shipment; local warehouse movements do not |
| **ReusableAsset – ReturnAuthorization** | 1:N | Optional | Assets are returned across circular lifecycle loops |
| **ReturnAuthorization – Inspection** | 1:N | Optional | Returned units undergo intake diagnostic assessment |
| **Inspection – Repair** | 1:N | Optional | Grade C and F assets trigger maintenance work orders |
| **ReusableAsset – DepositLedger** | 1:N | Optional | Double-entry financial audit trail (charges, refunds, adjustments) |
| **Shipment – DepositLedger** | 1:N | Optional | Deposits escrowed upon outbound transit dispatch |

---

## Lifecycle State Machines

### 1. Reusable Asset Lifecycle
```
[AVAILABLE] ──dispatch──> [IN_TRANSIT] ──delivery──> [DELIVERED / IN_USE]
     ▲                                                         │
     │                                                     return_req
     │                                                         │
     │                                                         ▼
[AVAILABLE] <──restock (Grade A/B)── [UNDER_INSPECTION] <── [RETURN_REQUESTED]
     ▲                                      │
     │                                 grade C/F
     │                                      ▼
[AVAILABLE] <──repair_complete────── [UNDER_REPAIR]
```
- **Disallowed Transitions:** 
  - An asset in `LOST` or `RETIRED` state cannot be dispatched.
  - An asset currently in `IN_TRANSIT` cannot be dispatched a second time before intake delivery.

### 2. Return Authorization (RMA) Lifecycle
```
[REQUESTED] ──> [APPROVED] ──> [RECEIVED] ──> [CLOSED]
       │             │
       └──cancelled──┴──rejected──> [CANCELLED / REJECTED]
```

### 3. Inspection Grading Matrix
Composite diagnostic score formula:
$$\text{Composite} = (\text{Cosmetic Score} \times 0.4) + (\text{Functional Score} \times 0.6)$$

| Grade | Composite Range | Condition Classification | Recommended Disposition | Financial Deposit Settlement |
|---|---|---|---|---|
| **Grade A** | 8.5 – 10.0 | Good | Immediate Restock | 100% Full Deposit Refund |
| **Grade B** | 6.5 – 8.4 | Minor Wear | Restock After Sanitization | 90% Deposit Refund (10% Restocking Fee) |
| **Grade C** | 4.0 – 6.4 | Damaged | Refurbishment Work Order | 50% Refund / 50% Repair Allocation |
| **Grade F** | Below 4.0 | Unusable | Salvage / Scrap | 0% Refund (Deposit Forfeited to Replace Unit) |
