"""
Deterministic ID generators for the reverse logistics system.

These functions generate repeatable identifiers for assets,
shipments, tracking numbers, RMAs, and custody events.
"""

import hashlib


def generate_asset_id(index: int) -> str:
    """Generate a deterministic reusable asset ID."""
    return f"AST-{index:06d}"


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
    """Generate a deterministic shipment ID."""
    return f"SHP-{index:06d}"


def generate_tracking_number(carrier: str, index: int) -> str:
    """Generate a deterministic carrier tracking number."""
    carrier_code = carrier[:3].upper()
    raw = f"{carrier}:{index}".encode("utf-8")
    token = hashlib.sha256(raw).hexdigest()[:10].upper()

    return f"TRK-{carrier_code}-{token}"


def generate_rma_number(index: int) -> str:
    """Generate a deterministic return authorization number."""
    return f"RMA-2026-{index:06d}"


def generate_event_id(index: int) -> str:
    """Generate a deterministic custody event ID."""
    return f"EVT-{index:08d}"