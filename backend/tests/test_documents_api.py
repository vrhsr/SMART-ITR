from __future__ import annotations

import uuid
from typing import Any

import boto3
from botocore.stub import Stubber
from botocore.stub import ANY
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from core.settings import settings
from main import app
from models.base import Base
from models import Client, Firm
from models.enums import UserRole


def _make_token(*, user_id: uuid.UUID, firm_id: uuid.UUID, role: UserRole) -> str:
    payload = {
        "sub": str(user_id),
        "firm_id": str(firm_id),
        "role": role.value,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _setup_inmemory_db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return TestingSessionLocal()


def test_upload_url_and_confirm_flow(monkeypatch: Any) -> None:
    # Replace DB dependency with in-memory SQLite for this test.
    db = _setup_inmemory_db()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    from db import get_db as real_get_db

    app.dependency_overrides[real_get_db] = override_get_db

    firm = Firm(name="Test Firm")
    db.add(firm)
    db.commit()
    db.refresh(firm)

    client = Client(firm_id=firm.firm_id, full_name="Client A")
    db.add(client)
    db.commit()
    db.refresh(client)

    token = _make_token(user_id=uuid.uuid4(), firm_id=firm.firm_id, role=UserRole.staff)
    headers = {"Authorization": f"Bearer {token}"}

    # Stub presigned URL generation (avoid AWS credentials requirement)
    def fake_generate_upload_url(*, firm_id, client_id, filename, bucket, kms_key_id, expires_in_minutes=15):
        return {
            "upload_url": "https://example.com/presigned",
            "bucket": bucket,
            "key": f"firms/{firm_id}/clients/{client_id}/fake-{filename}",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }

    monkeypatch.setattr("api.documents.generate_client_upload_url", fake_generate_upload_url)

    # Stub S3 head_object for confirm
    s3 = boto3.client("s3", region_name=settings.aws_region)
    stubber = Stubber(s3)

    def fake_client(*args, **kwargs):
        return s3

    monkeypatch.setattr("api.documents.boto3.client", fake_client)
    stubber.activate()

    test_client = TestClient(app)

    resp = test_client.post(
        "/api/documents/upload-url",
        headers=headers,
        json={
            "client_id": str(client.id),
            "filename": "test.pdf",
            "content_type": "application/pdf",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    document_id = uuid.UUID(data["document_id"])
    assert "upload_url" in data

    # Stub head_object for confirm
    head_response = {
        "ContentLength": 1024,
        "ContentType": "application/pdf",
    }
    stubber.add_response(
        "head_object",
        head_response,
        expected_params={"Bucket": "smartitr-docs-ap-south-1", "Key": ANY},
    )

    confirm_resp = test_client.post(
        "/api/documents/confirm",
        headers=headers,
        json={"document_id": str(document_id)},
    )
    assert confirm_resp.status_code == 200
    body = confirm_resp.json()
    assert body["status"] == "uploaded"

    app.dependency_overrides.clear()

