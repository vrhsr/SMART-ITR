import uuid
import pytest
from sqlalchemy import select
from models.firm import Firm
from models.user import User
from models.enums import UserRole
from models.client import Client
from models.document import Document
from models.export_artifact import ExportArtifact

def _seed_firm(db, firm_name):
    f_id = uuid.uuid4()
    u_id = uuid.uuid4()
    firm = Firm(firm_id=f_id, name=firm_name)
    db.add(firm)
    db.flush()
    user = User(
        id=u_id, 
        firm_id=f_id, 
        email=f"{firm_name}@test.com", 
        role=UserRole.owner,
        is_active=True
    )
    db.add(user)
    db.commit()
    return f_id, u_id

def test_tenant_isolation_clients(client, db, auth_mock):
    """Verify Firm B cannot see Firm A's clients."""
    f1_id, u1_id = _seed_firm(db, "FirmA")
    f2_id, u2_id = _seed_firm(db, "FirmB")
    
    # 1. Firm A creates a client
    c1 = Client(firm_id=f1_id, full_name="A's Client")
    db.add(c1)
    db.commit()
    
    # 2. Firm B tries to fetch it
    auth_mock(u2_id, f2_id)
    resp = client.get(f"/api/v1/ca/clients/{c1.id}")
    assert resp.status_code == 404
    
    # 3. Firm B lists clients (should be empty)
    resp_list = client.get("/api/v1/ca/clients")
    assert resp_list.status_code == 200
    assert len(resp_list.json()["items"]) == 0

def test_tenant_isolation_documents(client, db, auth_mock):
    """Verify Firm B cannot see Firm A's documents."""
    f1_id, u1_id = _seed_firm(db, "FirmA")
    f2_id, u2_id = _seed_firm(db, "FirmB")
    
    c1 = Client(firm_id=f1_id, full_name="A")
    db.add(c1)
    db.flush()
    d1 = Document(
        firm_id=f1_id, client_id=c1.id, document_type="form16",
        filename="a.pdf", content_type="a/p", status="pending",
        s3_bucket="b", s3_key="k"
    )
    db.add(d1)
    db.commit()
    
    auth_mock(u2_id, f2_id)
    resp = client.get(f"/api/v1/ca/documents/{d1.id}")
    assert resp.status_code == 404

def test_firm_id_injection_protection(client, db, auth_mock):
    """
    SECURITY: Verify that even if a user tries to inject a different firm_id
    in the request body, the backend uses the firm_id from the JWT.
    """
    f1_id, u1_id = _seed_firm(db, "FirmA")
    f2_id, _ = _seed_firm(db, "FirmB")
    
    auth_mock(u1_id, f1_id)
    
    # Try to create a client for Firm B
    resp = client.post("/api/v1/ca/clients", json={
        "full_name": "Injected Client",
        "firm_id": str(f2_id) # Body injection attempt
    })
    
    assert resp.status_code == 201
    new_client_id = resp.json()["id"]
    
    # Verify the client was ACTUALLY created for Firm A (JWT wins)
    db.expire_all()
    c = db.scalar(select(Client).where(Client.id == uuid.UUID(new_client_id)))
    assert c.firm_id == f1_id
    assert c.firm_id != f2_id
