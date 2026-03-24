import os
import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AWS_REGION"] = "ap-south-1"
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["RAZORPAY_KEY_ID"] = "rzp_test_123"
os.environ["RAZORPAY_KEY_SECRET"] = "rzp_secret_123"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "whsec_test_123"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Patch the real db.py BEFORE any test module imports it
import db
db.engine = engine
db.SessionLocal = TestingSessionLocal

@pytest.fixture(autouse=True, scope="session")
def setup_test_db():
    import models
    from models.base import Base
    
    # Ensure all tables are registered
    print(f"DEBUG: Registered tables: {list(Base.metadata.tables.keys())}")
    Base.metadata.create_all(engine)
    print("DEBUG: Tables created.")
