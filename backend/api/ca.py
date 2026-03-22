from __future__ import annotations

import uuid
from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel
import sqlalchemy as sa
from sqlalchemy.orm import Session

from auth.dependencies import get_current_firm, get_current_user
from auth.jwt import AuthenticatedUser
from db import get_db
from models import AuditEvent, Client, Document, ExportArtifact
from services.exporter import generate_client_pdf_report, generate_excel_export, generate_itd_json

router = APIRouter(prefix="/api/ca", tags=["ca-dashboard"])


# --- Dashboard ---

@router.get("/dashboard")
def get_dashboard(
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get high-level metrics for the CA firm dashboard (flat shape matching frontend interface)."""
    firm_uuid = uuid.UUID(current_firm_id)
    now_utc = sa.func.now()

    total_clients = db.scalar(sa.select(sa.func.count(Client.id)).where(Client.firm_id == firm_uuid)) or 0
    pending_docs = db.scalar(
        sa.select(sa.func.count(Document.id)).where(
            Document.firm_id == firm_uuid, Document.status.in_(["pending", "uploaded", "processing", "extracted"])
        )
    ) or 0

    # "Processed today" = approved or ready_for_review docs with updated_at today (UTC)
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    processed_today = db.scalar(
        sa.select(sa.func.count(Document.id)).where(
            Document.firm_id == firm_uuid,
            Document.status.in_(["ready_for_review", "approved"]),
            Document.updated_at >= today_start,
        )
    ) or 0

    # Documents processed this calendar month
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    documents_this_month = db.scalar(
        sa.select(sa.func.count(Document.id)).where(
            Document.firm_id == firm_uuid,
            Document.status.in_(["ready_for_review", "approved"]),
            Document.updated_at >= month_start,
        )
    ) or 0

    # Recent audit activity — convert action to human-readable message
    recent_events = db.scalars(
        sa.select(AuditEvent)
        .where(AuditEvent.firm_id == firm_uuid)
        .order_by(AuditEvent.created_at.desc())
        .limit(10)
    ).all()

    _ACTION_LABELS: dict[str, str] = {
        "document_uploaded": "Document uploaded",
        "pipeline.completed": "AI processing completed",
        "document.field_override": "CA corrected a field",
        "document.approved": "Document approved by CA",
        "export.downloaded": "Export downloaded",
        "consent_given": "Client gave DPDP consent",
        "consent_revoked": "Client revoked consent",
        "data_erased": "Client data erased (DPDP request)",
    }

    activity = [
        {
            "id": str(event.id),
            "message": _ACTION_LABELS.get(event.action, event.action),
            "created_at": event.created_at.isoformat(),
        }
        for event in recent_events
    ]

    return {
        "total_clients": total_clients,
        "pending_documents": pending_docs,
        "processed_today": processed_today,
        "documents_this_month": documents_this_month,
        "recent_activity": activity,
    }

# --- Clients ---

@router.get("/clients")
def list_clients(
    search: str | None = None,
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all clients for the firm."""
    firm_uuid = uuid.UUID(current_firm_id)

    query = sa.select(Client).where(Client.firm_id == firm_uuid).order_by(Client.updated_at.desc())
    
    if search:
        query = query.where(Client.full_name.ilike(f"%{search}%") | Client.pan_last4.ilike(f"%{search}%"))

    clients = db.scalars(query).all()
    
    result = []
    for client in clients:
        doc_count = db.scalar(sa.select(sa.func.count(Document.id)).where(Document.client_id == client.id)) or 0
        result.append({
            "id": str(client.id),
            "full_name": client.full_name,
            "pan_last4": client.pan_last4,
            "last_activity": client.last_activity.isoformat() if client.last_activity else client.created_at.isoformat(),
            "document_count": doc_count,
            "status": "Action Required" if doc_count > 0 else "Pending Review"
        })

    return result


@router.get("/clients/{client_id}")
def get_client_detail(
    client_id: uuid.UUID,
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    firm_uuid = uuid.UUID(current_firm_id)

    client = db.scalar(sa.select(Client).where(Client.id == client_id, Client.firm_id == firm_uuid))
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    docs = db.scalars(sa.select(Document).where(Document.client_id == client_id).order_by(Document.created_at.desc())).all()
    
    documents = []
    for d in docs:
        documents.append({
            "id": str(d.id),
            "filename": d.filename,
            "type": d.document_type,
            "status": d.status,
            "created_at": d.created_at.isoformat(),
            "extracted_data": d.extracted_data,
            "tax_computation": d.tax_computation
        })

    return {
        "id": str(client.id),
        "full_name": client.full_name,
        "pan_last4": client.pan_last4,
        "created_at": client.created_at.isoformat(),
        "documents": documents
    }

# --- Document Review ---

class OverrideRequest(BaseModel):
    field_path: str
    new_value: Any

@router.post("/documents/{document_id}/override")
def override_extracted_field(
    document_id: uuid.UUID,
    payload: OverrideRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    firm_uuid = uuid.UUID(str(current_user.firm_id))
    
    doc = db.scalar(sa.select(Document).where(Document.id == document_id, Document.firm_id == firm_uuid))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    extracted = doc.extracted_data or {}
    
    # Simple top-level path or two-level path override logic
    parts = payload.field_path.split(".")
    
    if len(parts) == 1:
        extracted[parts[0]] = payload.new_value
    elif len(parts) == 2:
        if parts[0] not in extracted:
            extracted[parts[0]] = {}
        extracted[parts[0]][parts[1]] = payload.new_value
        
    # Mark that an override occurred
    extracted["_overridden_by_ca"] = True
    
    doc.extracted_data = extracted
    
    event = AuditEvent(
        firm_id=firm_uuid,
        actor_user_id=current_user.id,
        action="document.field_override",
        resource_type="document",
        resource_id=str(doc.id),
        metadata={"field": payload.field_path, "new_value_type": type(payload.new_value).__name__}
    )
    db.add(event)
    db.commit()
    
    return {"status": "success"}


@router.post("/documents/{document_id}/approve")
def approve_document(
    document_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """CA approves the extracted data."""
    firm_uuid = uuid.UUID(str(current_user.firm_id))
    
    doc = db.scalar(sa.select(Document).where(Document.id == document_id, Document.firm_id == firm_uuid))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    doc.status = "approved"
    
    client = db.scalar(sa.select(Client).where(Client.id == doc.client_id))
    
    # Automatically generate exports upon approval
    # (In a real system, background tasks would be safer here, but doing sync for simplicity)
    try:
        generate_excel_export(doc, client, db)
        generate_itd_json(doc, client, db)
        generate_client_pdf_report(doc, client, db)
    except Exception as e:
        # Don't block approval if export generation fails now, can retry later
        import logging
        logging.getLogger("smartitr").error(f"Generate exports failed: {e}")
    
    event = AuditEvent(
        firm_id=firm_uuid,
        actor_user_id=current_user.id,
        action="document.approved",
        resource_type="document",
        resource_id=str(doc.id)
    )
    db.add(event)
    db.commit()
    
    return {"status": "approved"}
    
    
# --- Export ---

@router.get("/documents/{document_id}/export/{artifact_type}")
def get_export_url(
    document_id: uuid.UUID,
    artifact_type: str,
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    firm_uuid = uuid.UUID(current_firm_id)
    
    artifact = db.scalar(
        sa.select(ExportArtifact)
        .where(
            ExportArtifact.document_id == document_id, 
            ExportArtifact.firm_id == firm_uuid,
            ExportArtifact.artifact_type == artifact_type
        )
    )
    
    if not artifact:
        raise HTTPException(status_code=404, detail=f"Export artifact {artifact_type} not found")
        
    import boto3
    from core.settings import settings
    
    s3 = boto3.client("s3", region_name=settings.aws_region)
    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": artifact.s3_bucket, "Key": artifact.s3_key},
        ExpiresIn=3600
    )
    
    return {"url": url}
