
from decimal import Decimal

from sqlalchemy import select

from src.database.connection import Base, SessionLocal, engine
from src.database.models import AssetType, Location, Owner


def seed_owners(session):
    owners = [
        {
            "owner_name": "ABC Logistics",
            "owner_type": "internal",
            "contact_email": "contact@abclogistics.example",
        },
        {
            "owner_name": "Global Packaging",
            "owner_type": "supplier",
            "contact_email": "contact@globalpackaging.example",
        },
        {
            "owner_name": "Reliable Supply Co",
            "owner_type": "customer",
            "contact_email": "contact@reliablesupply.example",
        },
    ]

    for data in owners:
        existing = session.scalar(
            select(Owner).where(Owner.owner_name == data["owner_name"])
        )
        if existing is None:
            session.add(Owner(**data))


def seed_locations(session):
    locations = [
        {
            "location_name": "Hyderabad Central Warehouse",
            "location_type": "warehouse",
            "city": "Hyderabad",
            "state": "Telangana",
            "country": "India",
        },
        {
            "location_name": "Bengaluru Distribution Center",
            "location_type": "distribution_center",
            "city": "Bengaluru",
            "state": "Karnataka",
            "country": "India",
        },
        {
            "location_name": "Mumbai Supplier Hub",
            "location_type": "supplier",
            "city": "Mumbai",
            "state": "Maharashtra",
            "country": "India",
        },
        {
            "location_name": "Chennai Customer Facility",
            "location_type": "customer",
            "city": "Chennai",
            "state": "Tamil Nadu",
            "country": "India",
        },
    ]

    for data in locations:
        existing = session.scalar(
            select(Location).where(
                Location.location_name == data["location_name"]
            )
        )
        if existing is None:
            session.add(Location(**data))


def seed_asset_types(session):
    asset_types = [
        {
            "type_name": "Reusable Plastic Pallet",
            "description": "Heavy-duty reusable plastic transport pallet.",
            "expected_return_days": 30,
            "deposit_amount": Decimal("1500.00"),
        },
        {
            "type_name": "Industrial Crate",
            "description": "Reusable industrial goods transportation crate.",
            "expected_return_days": 21,
            "deposit_amount": Decimal("800.00"),
        },
        {
            "type_name": "Reusable Shipping Box",
            "description": "Reusable box for product distribution.",
            "expected_return_days": 14,
            "deposit_amount": Decimal("300.00"),
        },
        {
            "type_name": "Logistics Container",
            "description": "Reusable container for bulk material movement.",
            "expected_return_days": 45,
            "deposit_amount": Decimal("5000.00"),
        },
        {
            "type_name": "Material Handling Equipment",
            "description": "Reusable warehouse handling equipment.",
            "expected_return_days": 30,
            "deposit_amount": Decimal("2500.00"),
        },
    ]

    for data in asset_types:
        existing = session.scalar(
            select(AssetType).where(AssetType.type_name == data["type_name"])
        )
        if existing is None:
            session.add(AssetType(**data))


def seed_master_data():
    # Importing models above registers all tables with Base.metadata.
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()

    try:
        seed_owners(session)
        seed_locations(session)
        seed_asset_types(session)

        session.commit()
        print("Master data seeded successfully!")

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    seed_master_data()
