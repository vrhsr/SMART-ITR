import uuid
import pytest
from fastapi.testclient import TestClient

from main import app
from db import get_db, SessionLocal
from models import Firm, Client, Document

from auth.dependencies import get_current_user, get_current_firm
from auth.jwt import AuthenticatedUser
from jose import jwt
from core.settings import settings
from models.enums import UserRole

MOCK_FIRM_ID = uuid.uuid4()
MOCK_USER_ID = uuid.uuid4()
MOCK_CLIENT_ID = uuid.uuid4()

def _make_token():
    payload = {
        "sub": str(MOCK_USER_ID),
        "firm_id": str(MOCK_FIRM_ID),
        "role": UserRole.admin.value,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

client = TestClient(app, headers={"Authorization": f"Bearer {_make_token()}"})


def mock_get_current_firm():
    return str(MOCK_FIRM_ID)

def mock_get_current_user():
    from models.enums import UserRole
    return AuthenticatedUser(
        user_id=MOCK_USER_ID,
        firm_id=MOCK_FIRM_ID,
        role=UserRole.admin
    )

app.dependency_overrides[get_current_firm] = mock_get_current_firm
app.dependency_overrides[get_current_user] = mock_get_current_user


@pytest.fixture(scope="module")
def setup_db():
    db = SessionLocal()
    
    firm = Firm(firm_id=MOCK_FIRM_ID, name="Test Firm")
    db.add(firm)
    
    c = Client(id=MOCK_CLIENT_ID, firm_id=MOCK_FIRM_ID, full_name="John Doe", pan_last4="1234")
    db.add(c)
    
    doc = Document(
        firm_id=MOCK_FIRM_ID, 
        client_id=MOCK_CLIENT_ID, 
        document_type="form16", 
        filename="test.pdf", 
        content_type="application/pdf", 
        s3_bucket="test", 
        s3_key="test"
    )
    db.add(doc)
    db.commit()
    
    yield db
    
    # Teardown
    db.delete(doc)
    db.delete(c)
    db.delete(firm)
    db.commit()
    db.close()


def test_get_dashboard(setup_db):
    response = client.get("/api/ca/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["total_clients"] == 1
    assert data["pending_documents"] == 1


def test_list_clients(setup_db):
    response = client.get("/api/ca/clients")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "John Doe"
    assert data[0]["documents_uploaded"] == 1


def test_get_client_detail(setup_db):
    response = client.get(f"/api/ca/clients/{str(MOCK_CLIENT_ID)}")
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "John Doe"
    assert len(data["documents"]) == 1
    assert data["documents"][0]["type"] == "form16"


def test_approve_document_not_found():
    response = client.post(f"/api/ca/documents/{uuid.uuid4()}/approve")
    assert response.status_code == 404
