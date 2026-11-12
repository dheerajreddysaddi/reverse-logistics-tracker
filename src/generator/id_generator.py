"""
Deterministic ID generators for ReLoop 360 reverse logistics platform.

These functions generate repeatable, zero-padded identifiers for assets,
shipments, tracking numbers, RMAs, repairs, and custody events.
Conforms strictly to the deterministic ID conventions.
"""

import hashlib


def generate_asset_id(index: int) -> str:
    """Generate a deterministic reusable asset ID (AST-000001 format)."""
    return f"AST-{index:06d}"


def generate_reusable_asset_id(index: int) -> str:
    """Standard ReLoop 360 enterprise format (ASSET-0000001)."""
    return f"ASSET-{index:07d}"


def generate_serial_number(asset_type: str, index: int) -> str:
    """Generate a deterministic serial number for an asset."""
    tag = "".join(
        word[0].upper()
        for word in asset_type.split()
        if word
    )[:3]

    raw = f"{asset_type}:{index}".encode("utf-8")
    token = hashlib.sha256(raw).hexdigest()[:6].upper()

    return f"SN-{tag}-{token}-{index:06d}"


def generate_shipment_id(index: int) -> str:
    """Generate a deterministic shipment ID (SHP-000001 format)."""
    return f"SHP-{index:06d}"


def generate_reusable_shipment_id(index: int) -> str:
    """Standard ReLoop 360 enterprise format (SHP-2026-000001)."""
    return f"SHP-2026-{index:06d}"


def generate_tracking_number(carrier: str, index: int) -> str:
    """Generate a deterministic carrier tracking number."""
    carrier_code = carrier[:3].upper()
    raw = f"{carrier}:{index}".encode("utf-8")
    token = hashlib.sha256(raw).hexdigest()[:10].upper()

    return f"TRK-{carrier_code}-{token}"


def generate_rma_number(index: int) -> str:
    """Generate a deterministic return authorization number (RMA-2026-000001)."""
    return f"RMA-2026-{index:06d}"


def generate_custody_event_id(asset_code: str, event_index: int) -> str:
    """Generate a deterministic custody event ID (CUST-ASSET-0000001-000001)."""
    return f"CUST-{asset_code}-{event_index:06d}"


def generate_event_id(index: int) -> str:
    """Generate a sequential custody event ID."""
    return f"EVT-{index:08d}"


def generate_repair_code(index: int) -> str:
    """Generate a deterministic repair code (REP-2026-000001)."""
    return f"REP-2026-{index:06d}"
