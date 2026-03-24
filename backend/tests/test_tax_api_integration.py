import uuid
import pytest
from models.firm import Firm
from models.user import User
from models.enums import UserRole
from models.client import Client
from models.document import Document

def _setup_test_data(db, auth_mock):
    """Helper to setup a firm, user, and mock auth."""
    firm_id = uuid.uuid4()
    user_id = uuid.uuid4()
    
    firm = Firm(firm_id=firm_id, name="Test Firm")
    db.add(firm)
    db.flush()
    
    user = User(
        id=user_id,
        firm_id=firm_id,
        email="test@test.com",
        full_name="Test User",
        role=UserRole.owner,
        is_active=True
    )
    db.add(user)
    db.commit()
    
    auth_mock(user_id, firm_id, UserRole.owner)
    return firm_id, user_id

def test_override_then_recompute_flow(client, db, auth_mock):
    """
    Test the critical CA workflow:
    1. AI extracts data (simulated by seeding DB)
    2. CA views tax computation (GET /tax)
    3. CA overrides a field (POST /override)
    4. CA recomputes tax (POST /recompute)
    5. CA verifies updated tax (GET /tax)
    """
    firm_id, user_id = _setup_test_data(db, auth_mock)
    
    # 1. Create a client and a document with base data
    client_obj = Client(firm_id=firm_id, full_name="John Doe")
    db.add(client_obj)
    db.commit()
    db.refresh(client_obj)
    
    doc = Document(
        firm_id=firm_id,
        client_id=client_obj.id,
        document_type="form16",
        filename="f16.pdf",
        content_type="application/pdf",
        status="approved",
        s3_bucket="bucket",
        s3_key="key",
        extracted_data={
            "total_income_paise": 1100000 * 100, # 11L
            "deductions": {"section_80c_paise": 150000 * 100}
        }
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    # 2. GET /api/v1/ca/clients/{id}/tax
    resp_tax = client.get(f"/api/v1/ca/clients/{client_obj.id}/tax")
    assert resp_tax.status_code == 200
    initial_tax = resp_tax.json()["new_regime"]["total_tax_paise"]
    
    # 3. POST /api/v1/ca/documents/{id}/override
    # Increase income to 13L (crosses 12L rebate cliff)
    override_payload = {
        "field_path": "total_income_paise",
        "new_value": 1300000 * 100
    }
    resp_override = client.post(
        f"/api/v1/ca/documents/{doc.id}/override",
        json=override_payload
    )
    assert resp_override.status_code == 200
    
    # 4. POST /api/v1/ca/clients/{id}/tax/recompute
    # (The endpoint currently takes client_id, not doc_id)
    resp_recompute = client.post(f"/api/v1/ca/clients/{client_obj.id}/tax/recompute")
    assert resp_recompute.status_code == 200
    
    # 5. GET /api/v1/ca/clients/{id}/tax (verify it changed)
    resp_final = client.get(f"/api/v1/ca/clients/{client_obj.id}/tax")
    assert resp_final.status_code == 200
    final_tax = resp_final.json()["new_regime"]["total_tax_paise"]
    
    assert final_tax != initial_tax
    # With 13L income, tax should be significantly higher than 11L (due to rebate cliff)
    assert final_tax > initial_tax
