import pytest
from db import engine
from models.base import Base
import models # ensure all models are imported so Base metadata is populated

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables before all tests run, drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
