from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from auth.client_auth import ClientToken, get_current_client
from core.settings import settings
from db import get_db
from models import AuditEvent, Client, ConsentRecord, Document, ExportArtifact
import sqlalchemy as sa

router = APIRouter()


class ConsentRequest(BaseModel):
    consent_text_version: str


@router.post("/consent")
def give_consent(
    payload: ConsentRequest,
    request: Request,
    client: ClientToken = Depends(get_current_client),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    client_row: Client | None = db.scalar(
        select(Client).where(Client.id == client.client_id, Client.firm_id == client.firm_id)
    )
    if client_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    ip = request.client.host if request.client else None
    now = datetime.now(timezone.utc)

    record = ConsentRecord(
        firm_id=client.firm_id,
        client_id=client.client_id,
        purpose="tax_processing",
        consent_text_version=payload.consent_text_version,
        ip_address=ip,
        given_at=now,
    )
    db.add(record)

    audit = AuditEvent(
        firm_id=client.firm_id,
        actor_user_id=None,
        action="consent_given",
        resource_type="client",
        resource_id=str(client.client_id),
        details={"purpose": "tax_processing", "version": payload.consent_text_version},
    )
    db.add(audit)
    db.commit()

    return {"status": "ok", "given_at": now.isoformat()}


@router.post("/consent/revoke")
def revoke_consent(
    client: ClientToken = Depends(get_current_client),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    record: ConsentRecord | None = db.scalar(
        select(ConsentRecord)
        .where(
            ConsentRecord.client_id == client.client_id,
            ConsentRecord.firm_id == client.firm_id,
            ConsentRecord.purpose == "tax_processing",
            ConsentRecord.revoked_at.is_(None),
        )
        .order_by(ConsentRecord.given_at.desc())
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent not found")

    now = datetime.now(timezone.utc)
    record.revoked_at = now
    db.add(record)

    audit = AuditEvent(
        firm_id=client.firm_id,
        actor_user_id=None,
        action="consent_revoked",
        resource_type="client",
        resource_id=str(client.client_id),
        details={"purpose": "tax_processing"},
    )
    db.add(audit)
    db.commit()

    return {"status": "revoked", "revoked_at": now.isoformat()}


def _ensure_consent_exists(db: Session, *, client: ClientToken) -> None:
    exists = db.scalar(
        select(ConsentRecord.id).where(
            ConsentRecord.client_id == client.client_id,
            ConsentRecord.firm_id == client.firm_id,
            ConsentRecord.purpose == "tax_processing",
            ConsentRecord.revoked_at.is_(None),
        )
    )
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active consent found for processing tax data.",
        )


@router.get("/my-data")
def get_my_data(
    client: ClientToken = Depends(get_current_client),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_consent_exists(db, client=client)

    client_row: Client | None = db.scalar(
        select(Client).where(Client.id == client.client_id, Client.firm_id == client.firm_id)
    )
    if client_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    documents = list(
        db.scalars(
            select(Document).where(Document.client_id == client.client_id, Document.firm_id == client.firm_id)
        )
    )
    exports = list(
        db.scalars(
            select(ExportArtifact).where(
                ExportArtifact.client_id == client.client_id,  # type: ignore[attr-defined]
                ExportArtifact.firm_id == client.firm_id,
            )
        )
    )

    # Audit events associated via document IDs.
    doc_ids = [str(d.id) for d in documents]
    audit_events = list(
        db.scalars(
            select(AuditEvent).where(
                AuditEvent.firm_id == client.firm_id,
                AuditEvent.resource_type == "document",
                AuditEvent.resource_id.in_(doc_ids),
            )
        )
    )

    return {
        "client": {
            "id": str(client_row.id),
            "full_name": client_row.full_name,
            "pan_last4": client_row.pan_last4,
        },
        "documents": [
            {
                "id": str(d.id),
                "filename": d.filename,
                "status": d.status,
                "created_at": d.created_at.isoformat(),
            }
            for d in documents
        ],
        "exports": [
            {
                "id": str(e.id),
                "artifact_type": e.artifact_type,
                "created_at": e.created_at.isoformat(),
            }
            for e in exports
        ],
        "audit_events": [
            {
                "id": str(a.id),
                "action": a.action,
                "resource_type": a.resource_type,
                "resource_id": a.resource_id,
                "created_at": a.created_at.isoformat(),
            }
            for a in audit_events
        ],
        "tax_computations": [],  # placeholder until persisted separately
    }


@router.delete("/my-data")
def delete_my_data(
    client: ClientToken = Depends(get_current_client),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_consent_exists(db, client=client)

    documents = list(
        db.scalars(
            select(Document).where(Document.client_id == client.client_id, Document.firm_id == client.firm_id)
        )
    )

    # Ensure PDFs are deleted; if not, delete now.
    s3 = boto3.client("s3", region_name=settings.aws_region)
    for d in documents:
        if not d.pdf_deleted:
            try:
                s3.delete_object(Bucket=d.s3_bucket, Key=d.s3_key)
            except Exception:
                # If deletion fails, we still proceed but mark document as deleted attempt.
                pass
            d.pdf_deleted = True
            d.pdf_deleted_at = datetime.now(timezone.utc)
            db.add(d)

    # Delete structured data in dependency order.
    db.execute(
        sa.delete(ExportArtifact).where(
            ExportArtifact.document_id.in_([d.id for d in documents]),
            ExportArtifact.firm_id == client.firm_id,
        )
    )
    db.execute(
        sa.delete(Document).where(
            Document.client_id == client.client_id,
            Document.firm_id == client.firm_id,
        )
    )

    # Optionally keep Client record with minimal info, but clear last_activity.
    client_row: Client | None = db.scalar(
        select(Client).where(Client.id == client.client_id, Client.firm_id == client.firm_id)
    )
    if client_row:
        client_row.last_activity = None
        db.add(client_row)

    now = datetime.now(timezone.utc)
    audit = AuditEvent(
        firm_id=client.firm_id,
        actor_user_id=None,
        action="data_erased",
        resource_type="client",
        resource_id=str(client.client_id),
        details={"by": "client_request", "erased_at": now.isoformat()},
    )
    db.add(audit)

    db.commit()

    return {"status": "erased", "erased_at": now.isoformat()}

