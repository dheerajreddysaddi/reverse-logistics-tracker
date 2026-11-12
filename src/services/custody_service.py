
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from src.database.models import (
    ReusableAsset,
    CustodyEvent,
    Location,
    Shipment,
)


class CustodyService:
    """
    Reconstructs the movement history and current custody
    information of reusable assets using custody events.
    """

    @staticmethod
    def get_asset_trajectory(
        db: Session,
        asset_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns the complete chronological custody history
        and reconstructed location of an asset.
        """

        # Step 1: Find the asset
        asset = (
            db.query(ReusableAsset)
            .filter(ReusableAsset.asset_id == asset_id)
            .first()
        )

        if not asset:
            return None

        # Step 2: Fetch custody events chronologically
        events = (
            db.query(CustodyEvent)
            .filter(CustodyEvent.asset_id == asset_id)
            .order_by(
                CustodyEvent.event_timestamp.asc(),
                CustodyEvent.event_id.asc(),
            )
            .all()
        )

        history: List[Dict[str, Any]] = []
        location_cache = {}

        # Helper to fetch and cache location names
        def get_location(location_id):
            if location_id is None:
                return None

            if location_id not in location_cache:
                location = (
                    db.query(Location)
                    .filter(
                        Location.location_id == location_id
                    )
                    .first()
                )

                location_cache[location_id] = (
                    location.location_name if location else "Unknown"
                )

            return location_cache[location_id]

        # Step 3: Build the event timeline
        for event in events:

            from_location = get_location(
                event.from_location_id
            )

            to_location = get_location(
                event.to_location_id
            )

            shipment_code = None

            if event.shipment_id is not None:
                shipment = (
                    db.query(Shipment)
                    .filter(
                        Shipment.shipment_id == event.shipment_id
                    )
                    .first()
                )

                if shipment:
                    shipment_code = shipment.shipment_code

            history.append({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "event_timestamp": (
                    event.event_timestamp.isoformat()
                ),
                "from_location": from_location,
                "to_location": to_location,
                "actor_name": event.actor_name,
                "shipment_code": shipment_code,
                "notes": event.notes,
            })

        # Step 4: Reconstruct the latest known location
        if events:

            latest_event = events[-1]

            current_location = get_location(
                latest_event.to_location_id
            )

            current_custodian = latest_event.actor_name

            is_in_transit = (
                latest_event.event_type in ["dispatch", "transfer"]
            )

            if is_in_transit:
                location_description = (
                    f"In transit - last recorded at "
                    f"{current_location}"
                )
            else:
                location_description = (
                    f"Located at {current_location}"
                )

            last_event_time = (
                latest_event.event_timestamp.isoformat()
            )

        else:
            current_location = "Unknown"
            current_custodian = "Unknown"
            is_in_transit = False

            location_description = (
                "No custody events recorded for this asset."
            )

            last_event_time = None

        # Step 5: Return reconstructed asset information
        return {
            "asset_id": asset.asset_id,
            "asset_code": asset.asset_code,
            "serial_number": asset.serial_number,
            "lifecycle_status": asset.lifecycle_status,
            "current_location": current_location,
            "current_location_description": location_description,
            "is_in_transit": is_in_transit,
            "current_custodian": current_custodian,
            "last_event_time": last_event_time,
            "total_events": len(history),
            "trajectory": history,
        }
