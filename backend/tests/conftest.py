import pytest
import os
import uuid
import sys
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Ensure backend root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app
from models.base import Base
from db import get_db
from auth.dependencies import get_current_user, get_current_firm
from auth.jwt import AuthenticatedUser
from models.enums import UserRole
from core.settings import settings

TEST_DB = "test_smartitr.db"

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    settings.jwt_secret = "test-secret-key-32-characters-long"
    settings.debug = True
    settings.environment = "test"
    settings.database_url = f"sqlite:///{TEST_DB}"

@pytest.fixture(scope="function")
def engine():
    # Use a relative path to avoid permission issues in some environments
    db_path = os.path.join(os.getcwd(), TEST_DB)
    eng = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )
    
    @event.listens_for(eng, "connect")
    def enable_fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
    
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

@pytest.fixture(scope="function")
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture(scope="function")
def client(db):
    # Override database
    def override_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_db
    
    with TestClient(app, headers={"X-Test-Skip-Auth": "true"}) as c:
        yield c
    
    app.dependency_overrides.clear()

@pytest.fixture
def auth_mock():
    """
    Usage in test:
    def test_something(client, auth_mock):
        user = auth_mock("user_uuid", "firm_uuid", UserRole.admin)
        client.get(...)
    """
    def _mock(user_id: str, firm_id: str, role: UserRole = UserRole.owner):
        u_id = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        f_id = uuid.UUID(firm_id) if isinstance(firm_id, str) else firm_id
        
        mock_user = AuthenticatedUser(
            user_id=u_id,
            firm_id=f_id,
            role=role
        )
        
        def get_mock_user():
            return mock_user
            
        def get_mock_firm():
            return str(f_id)
            
        app.dependency_overrides[get_current_user] = get_mock_user
        app.dependency_overrides[get_current_firm] = get_mock_firm
        return mock_user
        
    return _mock
