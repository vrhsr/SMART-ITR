from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import boto3
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
import sqlalchemy as sa
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from db import get_db
from models import AuditEvent, Client, ConsentRecord, Document, ExportArtifact
from services.s3_signed_url import generate_client_upload_url
from agents.pipeline import run_document_pipeline
from auth.jwt import AuthenticatedUser
from auth.dependencies import get_current_firm, get_current_user
from core.settings import settings

router = APIRouter()

MAX_FILE_BYTES = 50 * 1024 * 1024
ALLOWED_CONTENT_TYPE = "application/pdf"
MAX_UPLOADS_PER_FIRM_PER_HOUR = 20


class UploadUrlRequest(BaseModel):
    client_id: uuid.UUID
    filename: str
    content_type: str


class ConfirmUploadRequest(BaseModel):
    document_id: uuid.UUID


def _is_pdf_filename(filename: str) -> bool:
    return filename.lower().endswith(".pdf")


def _count_recent_uploads(*, db: Session, firm_id: uuid.UUID) -> int:
    """
    Count upload-url issues in the last hour for a firm.

    This is DB-backed to work across instances (unlike in-memory counters).
    """

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    stmt = (
        select(func.count(Document.id))
        .where(
            Document.firm_id == firm_id,
            Document.created_at >= one_hour_ago,  # type: ignore[operator]
        )
    )
    return int(db.scalar(stmt) or 0)


@router.post("/upload-url")
def create_upload_url(
    *,
    payload: UploadUrlRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Generate a pre-signed S3 upload URL for a client document.
    """

    firm_uuid = current_user.firm_id
    if str(firm_uuid) != current_firm_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied")

    client_id = payload.client_id
    filename = payload.filename
    content_type = payload.content_type

    if not _is_pdf_filename(filename):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF uploads are allowed")

    # Server-side content-type guard; actual bytes validated in confirm.
    if content_type != ALLOWED_CONTENT_TYPE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF uploads are allowed")

    recent_count = _count_recent_uploads(db=db, firm_id=firm_uuid)
    if recent_count >= MAX_UPLOADS_PER_FIRM_PER_HOUR:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Upload rate limit exceeded")

    client: Client | None = db.scalar(
        select(Client).where(Client.id == client_id, Client.firm_id == firm_uuid),
    )
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    bucket = f"smartitr-docs-{settings.aws_region}"
    kms_key_id = "alias/smartitr-docs"

    presigned = generate_client_upload_url(
        firm_id=firm_uuid,
        client_id=client_id,
        filename=filename,
        bucket=bucket,
        kms_key_id=kms_key_id,
        expires_in_minutes=15,
    )

    document = Document(
        firm_id=firm_uuid,
        client_id=client_id,
        document_type="unknown",
        filename=filename,
        content_type=content_type,
        s3_bucket=bucket,
        s3_key=presigned["key"],
        kms_key_id=kms_key_id,
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Never log the key/path.
    return {
        "upload_url": presigned["upload_url"],
        "document_id": str(document.id),
        "expires_at": presigned["expires_at"],
    }


@router.post("/confirm")
def confirm_upload(
    *,
    payload: ConfirmUploadRequest,
    background_tasks: BackgroundTasks,
    current_user: AuthenticatedUser = Depends(get_current_user),
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Confirm that a document has been uploaded to S3 and trigger processing.
    """

    firm_uuid = current_user.firm_id
    if str(firm_uuid) != current_firm_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied")

    document_id = payload.document_id
    document: Document | None = db.scalar(
        select(Document).where(Document.id == document_id, Document.firm_id == firm_uuid),
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    s3 = boto3.client("s3", region_name=settings.aws_region)
    try:
        head = s3.head_object(Bucket=document.s3_bucket, Key=document.s3_key)
    except Exception as exc:  # pragma: no cover - network errors abstracted
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file not found") from exc

    size = head.get("ContentLength", 0)
    if size > MAX_FILE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File exceeds maximum size of 50MB")

    mime = head.get("ContentType") or ""
    if mime != ALLOWED_CONTENT_TYPE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF uploads are allowed")

    document.status = "uploaded"
    document.size_bytes = size
    db.add(document)

    audit = AuditEvent(
        firm_id=firm_uuid,
        actor_user_id=current_user.user_id,
        action="document_uploaded",
        resource_type="document",
        resource_id=str(document.id),
        details={"size_bytes": size, "content_type": mime},
    )
    db.add(audit)

    db.commit()

    # Trigger LangGraph pipeline in background
    background_tasks.add_task(
        run_document_pipeline,
        document_id=str(document.id),
        firm_id=str(firm_uuid),
        s3_key=document.s3_key,
    )

    return {"status": "uploaded", "document_id": str(document.id)}

