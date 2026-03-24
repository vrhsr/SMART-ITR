"""
Client-level export endpoints.

POST   /api/v1/ca/clients/{client_id}/exports           — Trigger export generation
GET    /api/v1/ca/clients/{client_id}/exports           — List all exports for a client
GET    /api/v1/ca/exports/{export_id}/download          — Pre-signed S3 download URL
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import boto3
import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import get_current_firm, get_current_user
from auth.jwt import AuthenticatedUser
from core.settings import settings
from db import get_db
from models import AuditEvent, Client, Document, ExportArtifact
from schemas.base import ErrorCodes

router = APIRouter()

EXPORT_PRESIGN_EXPIRY_SECONDS = 15 * 60  # 15 minutes


class CreateExportRequest(BaseModel):
    artifact_type: str  # itdx_json | excel | client_report_pdf


class ExportListItem(BaseModel):
    id: str
    artifact_type: str
    document_id: Optional[str]
    generated_by: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


def _get_client_or_404(db: Session, client_id: uuid.UUID, firm_uuid: uuid.UUID) -> Client:
    client = db.scalar(
        sa.select(Client).where(Client.id == client_id, Client.firm_id == firm_uuid)
    )
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": ErrorCodes.CLIENT_001, "message": "Client not found"},
        )
    return client


# ---------------------------------------------------------------------------
# POST /api/v1/ca/clients/{client_id}/exports
# ---------------------------------------------------------------------------

@router.post("/clients/{client_id}/exports", status_code=status.HTTP_202_ACCEPTED)
def trigger_export(
    client_id: uuid.UUID,
    payload: CreateExportRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Trigger export generation for a client.
    The export runs in the background; poll the list endpoint to check completion.
    """
    firm_uuid = current_user.firm_id
    client = _get_client_or_404(db, client_id, firm_uuid)

    valid_types = {"itdx_json", "excel", "client_report_pdf"}
    if payload.artifact_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "EXPORT_001",
                "message": f"artifact_type must be one of: {', '.join(valid_types)}",
            },
        )

    # Find the most recently approved document for this client
    doc = db.scalar(
        sa.select(Document).where(
            Document.client_id == client_id,
            Document.firm_id == firm_uuid,
            Document.status == "approved",
        ).order_by(Document.updated_at.desc())
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "EXPORT_002",
                "message": "No approved documents found for this client. Approve at least one document before exporting.",
            },
        )

    # Create a placeholder ExportArtifact record
    bucket = f"smartitr-exports-{settings.aws_region}"
    s3_key = f"exports/{firm_uuid}/{client_id}/{payload.artifact_type}/{uuid.uuid4()}"

    artifact = ExportArtifact(
        firm_id=firm_uuid,
        client_id=client_id,
        document_id=doc.id,
        artifact_type=payload.artifact_type,
        s3_bucket=bucket,
        s3_key=s3_key,
        generated_by="manual",
    )
    db.add(artifact)
    db.flush()  # get the generated artifact.id

    audit = AuditEvent(
        firm_id=firm_uuid,
        actor_user_id=current_user.user_id,
        action="export.triggered",
        resource_type="export_artifact",
        resource_id=str(artifact.id),
        details={"client_id": str(client_id), "type": payload.artifact_type},
    )
    db.add(audit)
    db.commit()
    db.refresh(artifact)

    # Kick off the actual export generation in the background
    from services.exporter import generate_excel_export, generate_itd_json, generate_client_pdf_report  # noqa: PLC0415
    if payload.artifact_type == "excel":
        background_tasks.add_task(generate_excel_export, doc, client, db)
    elif payload.artifact_type == "itdx_json":
        background_tasks.add_task(generate_itd_json, doc, client, db)
    elif payload.artifact_type == "client_report_pdf":
        background_tasks.add_task(generate_client_pdf_report, doc, client, db)

    return {
        "status": "accepted",
        "export_id": str(artifact.id),
        "artifact_type": payload.artifact_type,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/ca/clients/{client_id}/exports
# ---------------------------------------------------------------------------

@router.get("/clients/{client_id}/exports")
def list_exports(
    client_id: uuid.UUID,
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all export artifacts for a client."""
    firm_uuid = uuid.UUID(current_firm_id)
    _get_client_or_404(db, client_id, firm_uuid)

    artifacts = db.scalars(
        sa.select(ExportArtifact).where(
            ExportArtifact.client_id == client_id,
            ExportArtifact.firm_id == firm_uuid,
        ).order_by(ExportArtifact.created_at.desc())
    ).all()

    return [
        {
            "id": str(a.id),
            "artifact_type": a.artifact_type,
            "document_id": str(a.document_id) if a.document_id else None,
            "generated_by": a.generated_by,
            "created_at": a.created_at.isoformat(),
        }
        for a in artifacts
    ]


# ---------------------------------------------------------------------------
# GET /api/v1/ca/exports/{export_id}/download
# ---------------------------------------------------------------------------

@router.get("/exports/{export_id}/download")
def get_export_download_url(
    export_id: uuid.UUID,
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Generate a short-lived (15 min) pre-signed S3 GET URL for an export artifact.
    """
    firm_uuid = uuid.UUID(current_firm_id)

    artifact = db.scalar(
        sa.select(ExportArtifact).where(
            ExportArtifact.id == export_id,
            ExportArtifact.firm_id == firm_uuid,
        )
    )
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "EXPORT_003", "message": "Export artifact not found"},
        )

    try:
        s3 = boto3.client("s3", region_name=settings.aws_region)
        url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": artifact.s3_bucket, "Key": artifact.s3_key},
            ExpiresIn=EXPORT_PRESIGN_EXPIRY_SECONDS,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error_code": "EXPORT_004", "message": "Failed to generate download URL"},
        ) from exc

    expires_at = datetime.now(timezone.utc).timestamp() + EXPORT_PRESIGN_EXPIRY_SECONDS

    return {
        "url": url,
        "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
        "artifact_type": artifact.artifact_type,
    }
