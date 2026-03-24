import uuid
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from main import app
from db import get_db, SessionLocal
from models import Firm, Client, Document
from core.settings import settings
from models.enums import UserRole

@pytest.fixture
def client():
    return TestClient(app)

MOCK_FIRM_ID = uuid.uuid4()
MOCK_USER_ID = uuid.uuid4()
MOCK_CLIENT_ID = uuid.uuid4()

def _make_token(*, user_id: uuid.UUID, firm_id: uuid.UUID, role: UserRole) -> str:
    payload = {
        "sub": str(user_id),
        "firm_id": str(firm_id),
        "role": role.value,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

@pytest.fixture(scope="module")
def auth_headers():
    token = _make_token(user_id=MOCK_USER_ID, firm_id=MOCK_FIRM_ID, role=UserRole.admin)
    return {"Authorization": f"Bearer {token}"}


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


def test_get_dashboard(setup_db, auth_headers, client):
    response = client.get("/api/ca/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_clients"] == 1
    assert data["pending_documents"] == 1


def test_list_clients(setup_db, auth_headers, client):
    response = client.get("/api/ca/clients", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["full_name"] == "John Doe"
    assert data[0]["document_count"] == 1


def test_get_client_detail(setup_db, auth_headers, client):
    response = client.get(f"/api/ca/clients/{str(MOCK_CLIENT_ID)}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "John Doe"
    assert len(data["documents"]) == 1
    assert data["documents"][0]["type"] == "form16"


def test_approve_document_not_found(auth_headers, client):
    response = client.post(f"/api/ca/documents/{uuid.uuid4()}/approve", headers=auth_headers)
    assert response.status_code == 404
