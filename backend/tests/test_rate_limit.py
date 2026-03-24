from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.settings import settings
from main import app
from models import Client, Document, Firm
from models.base import Base
from models.enums import UserRole


def _make_token(*, firm_id: uuid.UUID) -> str:
    payload = {"sub": str(uuid.uuid4()), "firm_id": str(firm_id), "role": UserRole.staff.value}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def test_rate_limit_20_per_hour(monkeypatch) -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    from db import get_db as real_get_db

    app.dependency_overrides[real_get_db] = override_get_db

    firm = Firm(name="Firm")
    db.add(firm)
    db.commit()
    db.refresh(firm)

    client = Client(firm_id=firm.firm_id, full_name="Client")
    db.add(client)
    db.commit()
    db.refresh(client)

    # Avoid AWS in this test
    monkeypatch.setattr(
        "api.documents.generate_client_upload_url",
        lambda **kwargs: {"upload_url": "x", "bucket": "b", "key": "k", "expires_at": "t"},
    )

    test_client = TestClient(app)
    headers = {"Authorization": f"Bearer {_make_token(firm_id=firm.firm_id)}"}

    # Pre-seed 20 recent documents (counts as 20 upload-url issues)
    for _ in range(20):
        db.add(
            Document(
                firm_id=firm.firm_id,
                client_id=client.id,
                document_type="unknown",
                filename="a.pdf",
                content_type="application/pdf",
                s3_bucket="b",
                s3_key=str(uuid.uuid4()),
                kms_key_id="k",
                status="pending",
            )
        )
    db.commit()

    resp = test_client.post(
        "/api/documents/upload-url",
        headers=headers,
        json={"client_id": str(client.id), "filename": "test.pdf", "content_type": "application/pdf"},
    )
    assert resp.status_code == 429

    app.dependency_overrides.clear()

