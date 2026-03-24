from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from jose import jwt

from core.settings import settings
from main import app
from models.enums import UserRole


def _make_token(*, user_id: uuid.UUID, firm_id: uuid.UUID, role: UserRole) -> str:
    payload = {
        "sub": str(user_id),
        "firm_id": str(firm_id),
        "role": role.value,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def test_health_does_not_require_auth() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_me_requires_valid_token_and_returns_claims() -> None:
    client = TestClient(app)
    user_id = uuid.uuid4()
    firm_id = uuid.uuid4()
    token = _make_token(user_id=user_id, firm_id=firm_id, role=UserRole.admin)

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(user_id)
    assert body["firm_id"] == str(firm_id)
    assert body["role"] == UserRole.admin.value


def test_tenant_isolation_rejects_cross_firm_access() -> None:
    client = TestClient(app)
    firm_id = uuid.uuid4()
    other_firm_id = uuid.uuid4()
    token = _make_token(user_id=uuid.uuid4(), firm_id=firm_id, role=UserRole.staff)

    # Path tries to access another firm, but JWT firm_id should win and cause 403
    response = client.post(
        f"/firms/{other_firm_id}/example-action",
        headers={"Authorization": f"Bearer {token}"},
        json={"firm_id": str(other_firm_id)},
    )
    assert response.status_code == 403

    # Matching firm_id should succeed
    ok_response = client.post(
        f"/firms/{firm_id}/example-action",
        headers={"Authorization": f"Bearer {token}"},
        json={"firm_id": str(other_firm_id)},
    )
    assert ok_response.status_code == 200
    body = ok_response.json()
    assert body["firm_id"] == str(firm_id)

