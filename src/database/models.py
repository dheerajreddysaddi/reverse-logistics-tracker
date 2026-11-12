
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.database.connection import Base


# --------------------------------------------------
# 1. OWNERS
# --------------------------------------------------

class Owner(Base):
    __tablename__ = "owners"

    owner_id = Column(Integer, primary_key=True, index=True)
    owner_name = Column(String(150), nullable=False, unique=True)
    owner_type = Column(String(30), nullable=False)
    contact_email = Column(String(150), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    assets = relationship("ReusableAsset", back_populates="owner")


# --------------------------------------------------
# 2. LOCATIONS
# --------------------------------------------------

class Location(Base):
    __tablename__ = "locations"

    location_id = Column(Integer, primary_key=True, index=True)
    location_name = Column(String(150), nullable=False)
    location_type = Column(String(30), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    outgoing_shipments = relationship(
        "Shipment",
        foreign_keys="Shipment.origin_location_id",
        back_populates="origin",
    )

    incoming_shipments = relationship(
        "Shipment",
        foreign_keys="Shipment.destination_location_id",
        back_populates="destination",
    )


# --------------------------------------------------
# 3. ASSET TYPES
# --------------------------------------------------

class AssetType(Base):
    __tablename__ = "asset_types"

    asset_type_id = Column(Integer, primary_key=True, index=True)
    type_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    expected_return_days = Column(Integer, nullable=False)
    deposit_amount = Column(Numeric(12, 2), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "expected_return_days > 0",
            name="ck_asset_type_return_days",
        ),
        CheckConstraint(
            "deposit_amount >= 0",
            name="ck_asset_type_deposit",
        ),
    )

    assets = relationship("ReusableAsset", back_populates="asset_type")


# --------------------------------------------------
# 4. REUSABLE ASSETS
# --------------------------------------------------

class ReusableAsset(Base):
    __tablename__ = "reusable_assets"

    asset_id = Column(Integer, primary_key=True, index=True)
    asset_code = Column(String(50), nullable=False, unique=True)
    asset_type_id = Column(
        Integer,
        ForeignKey("asset_types.asset_type_id"),
        nullable=False,
    )
    owner_id = Column(
        Integer,
        ForeignKey("owners.owner_id"),
        nullable=False,
    )
    serial_number = Column(String(100), nullable=True)
    manufacture_date = Column(Date, nullable=True)
    lifecycle_status = Column(String(30), nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "lifecycle_status IN "
            "('available', 'in_transit', 'in_use', "
            "'under_repair', 'lost', 'retired')",
            name="ck_asset_lifecycle_status",
        ),
        Index("ix_asset_owner", "owner_id"),
        Index("ix_asset_type", "asset_type_id"),
    )

    asset_type = relationship("AssetType", back_populates="assets")
    owner = relationship("Owner", back_populates="assets")

    custody_events = relationship(
        "CustodyEvent",
        back_populates="asset",
    )

    return_authorizations = relationship(
        "ReturnAuthorization",
        back_populates="asset",
    )

    inspections = relationship(
        "Inspection",
        back_populates="asset",
    )

    repairs = relationship(
        "Repair",
        back_populates="asset",
    )

    deposit_entries = relationship(
        "DepositLedger",
        back_populates="asset",
    )


# --------------------------------------------------
# 5. SHIPMENTS
# --------------------------------------------------

class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id = Column(Integer, primary_key=True, index=True)
    shipment_code = Column(String(50), nullable=False, unique=True)

    origin_location_id = Column(
        Integer,
        ForeignKey("locations.location_id"),
        nullable=False,
    )

    destination_location_id = Column(
        Integer,
        ForeignKey("locations.location_id"),
        nullable=False,
    )

    carrier_name = Column(String(150), nullable=False)
    dispatch_date = Column(DateTime, nullable=False)
    expected_delivery_date = Column(DateTime, nullable=True)
    actual_delivery_date = Column(DateTime, nullable=True)
    shipment_status = Column(String(30), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "origin_location_id != destination_location_id",
            name="ck_shipment_different_locations",
        ),
        CheckConstraint(
            "shipment_status IN "
            "('planned', 'dispatched', 'delivered', 'cancelled')",
            name="ck_shipment_status",
        ),
        Index("ix_shipment_status", "shipment_status"),
    )

    origin = relationship(
        "Location",
        foreign_keys=[origin_location_id],
        back_populates="outgoing_shipments",
    )

    destination = relationship(
        "Location",
        foreign_keys=[destination_location_id],
        back_populates="incoming_shipments",
    )

    custody_events = relationship(
        "CustodyEvent",
        back_populates="shipment",
    )

    return_authorizations = relationship(
        "ReturnAuthorization",
        back_populates="shipment",
    )

    deposit_entries = relationship(
        "DepositLedger",
        back_populates="shipment",
    )


# --------------------------------------------------
# 6. CUSTODY EVENTS
# --------------------------------------------------

class CustodyEvent(Base):
    __tablename__ = "custody_events"

    event_id = Column(Integer, primary_key=True, index=True)

    asset_id = Column(
        Integer,
        ForeignKey("reusable_assets.asset_id"),
        nullable=False,
    )

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.shipment_id"),
        nullable=True,
    )

    from_location_id = Column(
        Integer,
        ForeignKey("locations.location_id"),
        nullable=True,
    )

    to_location_id = Column(
        Integer,
        ForeignKey("locations.location_id"),
        nullable=False,
    )

    actor_name = Column(String(150), nullable=False)
    event_type = Column(String(30), nullable=False)
    event_timestamp = Column(DateTime, nullable=False)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "event_type IN "
            "('dispatch', 'transfer', 'receipt', 'return')",
            name="ck_custody_event_type",
        ),
        Index("ix_custody_asset_timestamp", "asset_id", "event_timestamp"),
    )

    asset = relationship("ReusableAsset", back_populates="custody_events")
    shipment = relationship("Shipment", back_populates="custody_events")


# --------------------------------------------------
# 7. RETURN AUTHORIZATIONS
# --------------------------------------------------

class ReturnAuthorization(Base):
    __tablename__ = "return_authorizations"

    return_id = Column(Integer, primary_key=True, index=True)
    return_code = Column(String(50), nullable=False, unique=True)

    asset_id = Column(
        Integer,
        ForeignKey("reusable_assets.asset_id"),
        nullable=False,
    )

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.shipment_id"),
        nullable=True,
    )

    requested_by = Column(String(150), nullable=False)
    request_date = Column(DateTime, nullable=False)
    approved_date = Column(DateTime, nullable=True)
    return_status = Column(String(30), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "return_status IN "
            "('requested', 'approved', 'received', "
            "'rejected', 'cancelled')",
            name="ck_return_status",
        ),
    )

    asset = relationship(
        "ReusableAsset",
        back_populates="return_authorizations",
    )

    shipment = relationship(
        "Shipment",
        back_populates="return_authorizations",
    )

    inspections = relationship(
        "Inspection",
        back_populates="return_authorization",
    )


# --------------------------------------------------
# 8. INSPECTIONS
# --------------------------------------------------

class Inspection(Base):
    __tablename__ = "inspections"

    inspection_id = Column(Integer, primary_key=True, index=True)

    asset_id = Column(
        Integer,
        ForeignKey("reusable_assets.asset_id"),
        nullable=False,
    )

    return_id = Column(
        Integer,
        ForeignKey("return_authorizations.return_id"),
        nullable=True,
    )

    inspector_name = Column(String(150), nullable=False)
    inspection_date = Column(DateTime, nullable=False)
    condition_status = Column(String(30), nullable=False)
    remarks = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "condition_status IN "
            "('good', 'damaged', 'unusable')",
            name="ck_inspection_condition",
        ),
    )

    asset = relationship("ReusableAsset", back_populates="inspections")

    return_authorization = relationship(
        "ReturnAuthorization",
        back_populates="inspections",
    )

    repairs = relationship("Repair", back_populates="inspection")


# --------------------------------------------------
# 9. REPAIRS
# --------------------------------------------------

class Repair(Base):
    __tablename__ = "repairs"

    repair_id = Column(Integer, primary_key=True, index=True)

    asset_id = Column(
        Integer,
        ForeignKey("reusable_assets.asset_id"),
        nullable=False,
    )

    inspection_id = Column(
        Integer,
        ForeignKey("inspections.inspection_id"),
        nullable=False,
    )

    repair_description = Column(Text, nullable=False)
    repair_cost = Column(Numeric(12, 2), nullable=False)
    repair_status = Column(String(30), nullable=False)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "repair_cost >= 0",
            name="ck_repair_cost",
        ),
        CheckConstraint(
            "repair_status IN "
            "('open', 'in_progress', 'completed')",
            name="ck_repair_status",
        ),
    )

    asset = relationship("ReusableAsset", back_populates="repairs")

    inspection = relationship(
        "Inspection",
        back_populates="repairs",
    )


# --------------------------------------------------
# 10. DEPOSIT LEDGER
# --------------------------------------------------

class DepositLedger(Base):
    __tablename__ = "deposit_ledger"

    ledger_id = Column(Integer, primary_key=True, index=True)

    asset_id = Column(
        Integer,
        ForeignKey("reusable_assets.asset_id"),
        nullable=False,
    )

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.shipment_id"),
        nullable=True,
    )

    transaction_type = Column(String(30), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    transaction_date = Column(DateTime, nullable=False)
    reference_code = Column(String(100), nullable=False, unique=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "transaction_type IN "
            "('charge', 'refund', 'adjustment')",
            name="ck_deposit_transaction_type",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_deposit_amount",
        ),
        Index("ix_deposit_asset", "asset_id"),
    )

    asset = relationship(
        "ReusableAsset",
        back_populates="deposit_entries",
    )

    shipment = relationship(
        "Shipment",
        back_populates="deposit_entries",
    )
