"""Seed the database with a default firm and admin user for development."""
import uuid

from db import engine, SessionLocal
from models.base import Base
from models.firm import Firm
from models.user import User
from models.enums import UserRole
import models  # ensure all models registered

# Default IDs — always the same so the JWT works across restarts
FIRM_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")

def seed():
    db = SessionLocal()
    try:
        existing_firm = db.get(Firm, FIRM_ID)
        if existing_firm:
            print(f"Firm already exists: {existing_firm.name}")
        else:
            firm = Firm(firm_id=FIRM_ID, name="Demo CA Firm")
            db.add(firm)
            db.flush()
            print("Created firm: Demo CA Firm")

        existing_user = db.get(User, ADMIN_ID)
        if existing_user:
            print(f"Admin user already exists: {existing_user.email}")
        else:
            admin = User(
                id=ADMIN_ID,
                firm_id=FIRM_ID,
                email="admin@smartitr.com",
                full_name="Admin User",
                role=UserRole.owner,
                is_active=True,
            )
            db.add(admin)
            print("Created admin user: admin@smartitr.com")

        db.commit()
        print("\nSeed complete! Login with:")
        print("  Email:    admin@smartitr.com")
        print("  Password: (any non-empty string)")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
