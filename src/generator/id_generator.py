"""
Deterministic ID generators for Reverse Logistics & Asset Custody Control Tower.

These functions generate repeatable, immutable, zero-padded identifiers strictly
adhering to the mandated enterprise specifications:
- Asset: ASSET-0000001 (7 digits)
- Return Authorization: RMA-2026-000001 (6 digits)
- Shipment: SHP-2026-000001 (6 digits)
- Custody Event: CUST-ASSET-0000001-000001 (Asset Code + 6 digits counter)
- Repair: REP-2026-000001 (6 digits)
"""

import hashlib


def generate_asset_id(index: int) -> str:
    """Generate standardized enterprise asset identifier (ASSET-0000001 format)."""
    return f"ASSET-{index:07d}"


def generate_reusable_asset_id(index: int) -> str:
    """Alias for standardized enterprise asset identifier (ASSET-0000001 format)."""
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
    """Generate standardized enterprise shipment identifier (SHP-2026-000001 format)."""
    return f"SHP-2026-{index:06d}"


def generate_reusable_shipment_id(index: int) -> str:
    """Alias for standardized enterprise shipment identifier (SHP-2026-000001 format)."""
    return f"SHP-2026-{index:06d}"


def generate_tracking_number(carrier: str, index: int) -> str:
    """Generate a deterministic carrier tracking number."""
    carrier_code = carrier[:3].upper()
    raw = f"{carrier}:{index}".encode("utf-8")
    token = hashlib.sha256(raw).hexdigest()[:10].upper()

    return f"TRK-{carrier_code}-{token}"


def generate_rma_number(index: int) -> str:
    """Generate standardized return authorization identifier (RMA-2026-000001 format)."""
    return f"RMA-2026-{index:06d}"


def generate_custody_event_id(asset_code: str, event_index: int) -> str:
    """Generate standardized custody event identifier (CUST-ASSET-0000001-000001 format)."""
    return f"CUST-{asset_code}-{event_index:06d}"


def generate_event_id(index: int) -> str:
    """Generate sequential custody event identifier."""
    return f"EVT-2026-{index:06d}"


def generate_repair_code(index: int) -> str:
    """Generate standardized repair work order identifier (REP-2026-000001 format)."""
    return f"REP-2026-{index:06d}"
