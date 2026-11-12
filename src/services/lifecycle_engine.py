"""
Lifecycle Engine for Reusable Asset Management.
Enforces state machine transitions, validation rules, and audit logging.


Lifecycle states:
- available: Asset is ready for dispatch in inventory.
- dispatched: Assigned to a shipment manifest.
- in_transit: Physically moving with carrier.
- delivered: Reached destination facility or customer.
- in_use: Actively deployed with customer/tenant.
- return_requested: Return authorization issued.
- returned: Arrived back at return center dock.
- under_inspection: Technicians grading hardware condition.
- under_repair: Triage routed to refurbishment facility.
- damaged: Non-functional or impaired awaiting repair.
- lost: Unreturned past maximum threshold or declared missing.
- retired: Scrapped, recycled, or end-of-life.
- disputed: Custody handoff contested.
"""

from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.orm import Session

from src.database.models import (
    ReusableAsset,
    AssetType,
    Owner,
    CustodyEvent,
    Location,
)


# Permitted state transitions
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "available": ["dispatched", "in_transit", "retired"],
    "dispatched": ["in_transit", "cancelled", "available"],
    "in_transit": ["delivered", "lost", "disputed"],
    "delivered": ["in_use", "return_requested", "available"],
    "in_use": ["return_requested", "lost", "damaged"],
    "return_requested": ["returned", "in_transit", "lost"],
    "returned": ["under_inspection", "available"],
    "under_inspection": ["available", "under_repair", "damaged", "retired"],
    "damaged": ["under_repair", "retired"],
    "under_repair": ["under_inspection", "available", "retired"],
    "lost": ["available", "retired"],  # If found, can return to available
    "disputed": ["available", "in_use", "lost"],
    "retired": [],  # Terminal state
}


class LifecycleTransitionError(Exception):
    """Raised when an illegal asset lifecycle transition is attempted."""
    pass


class LifecycleEngine:

    @staticmethod
    def validate_transition(
        current_status: str,
        target_status: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates whether transitioning from current_status to target_status is permitted.
        """
        curr = (current_status or "").lower()
        target = (target_status or "").lower()

        if curr == "lost" and target in ["dispatched", "in_transit"]:
            return False, "Lost assets cannot be dispatched into transit."

        if curr == "retired":
            return False, "Retired assets are end-of-life and cannot transition to active states."

        if curr in ["in_transit", "dispatched"] and target in ["dispatched", "in_transit"]:
            return False, "Assets cannot be dispatched twice while already in transit."

        allowed = ALLOWED_TRANSITIONS.get(curr, [])
        if target not in allowed and curr != target:
            return False, (
                f"Invalid lifecycle transition: '{curr}' -> '{target}'. "
                f"Allowed next states from '{curr}': {allowed}"
            )

        return True, None

    @staticmethod
    def transition_asset_state(
        db: Session,
        asset_id: int,
        target_status: str,
        actor_name: str = "System Automated Engine",
        location_id: Optional[int] = None,
        notes: Optional[str] = None,
        effective_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Safely transitions an asset's lifecycle state, updating the database
        and recording an auditable CustodyEvent.
        """
        asset = (
            db.query(ReusableAsset)
            .filter(ReusableAsset.asset_id == asset_id)
            .first()
        )

        if not asset:
            raise ValueError(f"Asset ID {asset_id} does not exist.")

        curr_status = asset.lifecycle_status
        target_status = target_status.lower()

        is_valid, reason = LifecycleEngine.validate_transition(curr_status, target_status)
        if not is_valid:
            raise LifecycleTransitionError(reason)

        event_time = effective_time or datetime.utcnow()

        # Update asset status
        asset.lifecycle_status = target_status

        # Create auditable custody event
        event = CustodyEvent(
            asset_id=asset.asset_id,
            shipment_id=None,
            from_location_id=None,
            to_location_id=location_id or 1,
            actor_name=actor_name,
            event_type="transfer",
            event_timestamp=event_time,
            notes=notes or f"Lifecycle transition: {curr_status} -> {target_status}",
        )
        db.add(event)
        db.commit()
        db.refresh(asset)

        return {
            "asset_id": asset.asset_id,
            "asset_code": asset.asset_code,
            "previous_status": curr_status,
            "new_status": target_status,
            "timestamp": event_time.isoformat(),
            "actor": actor_name,
        }

    @staticmethod
    def can_dispatch(status: str) -> bool:
        """Determines if an asset in the given status is eligible for outbound dispatch."""
        st = (status or "").lower()
        return st in ["available"]

    @staticmethod
    def is_asset_overdue_lost(days_outstanding: int, threshold_days: int = 30) -> bool:
        """Determines if an overdue asset should be categorized as candidate lost."""
        return days_outstanding > threshold_days

    @staticmethod
    def calculate_outstanding_days(
        expected_return_date: Any,
        reference_date: Any,
    ) -> int:
        """
        Formula required by Section 9:
        days_outstanding = max(0, reference_date - expected_return_date)
        """
        if not reference_date or not expected_return_date:
            return 0
        ref_d = reference_date.date() if hasattr(reference_date, "date") else reference_date
        exp_d = expected_return_date.date() if hasattr(expected_return_date, "date") else expected_return_date
        diff_days = (ref_d - exp_d).days
        return max(0, diff_days)

    calculate_days_outstanding = calculate_outstanding_days
