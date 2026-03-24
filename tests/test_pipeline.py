from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents.pipeline import run_document_pipeline
from models import Client, Document, Firm
from models.base import Base


def test_pipeline_happy_path_with_mocks(monkeypatch) -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()

    # Ensure pipeline uses our test DB session factory
    monkeypatch.setattr("agents.pipeline.SessionLocal", SessionLocal)

    firm = Firm(name="Firm")
    db.add(firm)
    db.commit()
    db.refresh(firm)

    client = Client(firm_id=firm.firm_id, full_name="Client")
    db.add(client)
    db.commit()
    db.refresh(client)

    doc = Document(
        firm_id=firm.firm_id,
        client_id=client.id,
        document_type="unknown",
        filename="a.pdf",
        content_type="application/pdf",
        s3_bucket="b",
        s3_key="k",
        kms_key_id="kid",
        status="uploaded",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    monkeypatch.setattr("services.s3_documents.download_pdf_to_memory", lambda **kwargs: b"%PDF-1.4")
    monkeypatch.setattr("services.textract.textract_detect_text", lambda **kwargs: "Form 16 Salary")
    monkeypatch.setattr("services.bedrock.haiku_classify_document", lambda **kwargs: "form16")
    monkeypatch.setattr("services.textract.textract_analyze_tables", lambda **kwargs: {"Blocks": []})
    monkeypatch.setattr("services.bedrock.sonnet_explain_anomalies", lambda **kwargs: "ok")

    final = run_document_pipeline(document_id=str(doc.id), firm_id=str(firm.firm_id), s3_key=doc.s3_key)
    assert final.status in ("ready_for_review", "failed")

