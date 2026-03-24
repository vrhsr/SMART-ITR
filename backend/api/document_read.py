"""
Document read-path and status endpoints.

GET    /api/v1/ca/documents                   — List documents (paginated, filtered)
GET    /api/v1/ca/documents/{id}              — Full document detail
GET    /api/v1/ca/documents/{id}/status       — Pipeline processing status (polling)
DELETE /api/v1/ca/documents/{id}              — Soft-delete + S3 cleanup

The upload flow (POST /upload-url and POST /confirm) lives in documents.py
which is mounted at the same prefix by the router.
"""
from __future__ import annotations

import math
import uuid
from typing import Any, Optional

import boto3
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import get_current_firm, get_current_user
from auth.jwt import AuthenticatedUser
from core.settings import settings
from db import get_db
from models import AuditEvent, Document
from schemas.base import ErrorCodes, PaginatedResponse

router = APIRouter()

# LangGraph processing stages in order (for progress reporting)
STAGE_ORDER: dict[str, int] = {
    "classify": 1,
    "extract": 2,
    "validate": 3,
    "calculate": 4,
    "anomaly": 5,
    "export": 6,
}
TOTAL_STAGES = 6


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _get_doc_or_404(db: Session, document_id: uuid.UUID, firm_uuid: uuid.UUID) -> Document:
    doc = db.scalar(
        sa.select(Document).where(
            Document.id == document_id,
            Document.firm_id == firm_uuid,
        )
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": ErrorCodes.DOC_001, "message": "Document not found"},
        )
    return doc


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DocumentListItem(BaseModel):
    id: str
    filename: str
    document_type: str
    status: str
    processing_stage: Optional[str]
    client_id: str
    created_at: str

    model_config = {"from_attributes": True}


class ProcessingStatusResponse(BaseModel):
    document_id: str
    status: str
    current_stage: Optional[str]
    stage_number: int
    total_stages: int
    started_at: Optional[str]
    error: Optional[str]
    percent_complete: int


# ---------------------------------------------------------------------------
# GET /api/v1/ca/documents
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedResponse[DocumentListItem])
def list_documents(
    client_id: Optional[uuid.UUID] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    doc_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DocumentListItem]:
    """
    List documents with optional filters:
      ?client_id=UUID   — filter by client
      ?status=processing — filter by pipeline status
      ?doc_type=form16  — filter by document type
    """
    firm_uuid = uuid.UUID(current_firm_id)
    base_q = sa.select(Document).where(Document.firm_id == firm_uuid)

    if client_id:
        base_q = base_q.where(Document.client_id == client_id)
    if status_filter:
        base_q = base_q.where(Document.status == status_filter)
    if doc_type:
        base_q = base_q.where(Document.document_type == doc_type)

    total = db.scalar(sa.select(sa.func.count()).select_from(base_q.subquery())) or 0
    docs = db.scalars(
        base_q.order_by(Document.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    items = [
        DocumentListItem(
            id=str(d.id),
            filename=d.filename,
            document_type=d.document_type,
            status=d.status,
            processing_stage=d.processing_stage,
            client_id=str(d.client_id),
            created_at=d.created_at.isoformat(),
        )
        for d in docs
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=math.ceil(total / per_page) if total else 0,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/ca/documents/{document_id}
# ---------------------------------------------------------------------------

@router.get("/{document_id}")
def get_document(
    document_id: uuid.UUID,
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return full document detail including extracted fields and tax computation."""
    firm_uuid = uuid.UUID(current_firm_id)
    doc = _get_doc_or_404(db, document_id, firm_uuid)

    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "document_type": doc.document_type,
        "status": doc.status,
        "processing_stage": doc.processing_stage,
        "processing_started_at": doc.processing_started_at.isoformat() if doc.processing_started_at else None,
        "processing_error": doc.processing_error,
        "client_id": str(doc.client_id),
        "extracted_data": doc.extracted_data or {},
        "tax_computation": doc.tax_computation or {},
        "confidence_score": doc.confidence_score,
        "size_bytes": doc.size_bytes,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/ca/documents/{document_id}/status
# (Polling endpoint — frontend calls every 3s during processing)
# ---------------------------------------------------------------------------

@router.get("/{document_id}/status", response_model=ProcessingStatusResponse)
def get_processing_status(
    document_id: uuid.UUID,
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> ProcessingStatusResponse:
    """
    Lightweight status endpoint.  Frontend polls every 3 seconds.
    Stop polling when status is 'completed', 'approved', or 'failed'.
    """
    firm_uuid = uuid.UUID(current_firm_id)
    doc = _get_doc_or_404(db, document_id, firm_uuid)

    stage_num = STAGE_ORDER.get(doc.processing_stage or "", 0)
    pct = int((stage_num / TOTAL_STAGES) * 100) if doc.status == "processing" else (
        100 if doc.status in {"ready_for_review", "approved", "completed"} else 0
    )

    return ProcessingStatusResponse(
        document_id=str(doc.id),
        status=doc.status,
        current_stage=doc.processing_stage,
        stage_number=stage_num,
        total_stages=TOTAL_STAGES,
        started_at=doc.processing_started_at.isoformat() if doc.processing_started_at else None,
        error=doc.processing_error,
        percent_complete=pct,
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/ca/documents/{document_id}
# ---------------------------------------------------------------------------

@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Mark a document as deleted and schedule the S3 object for removal.
    Documents currently being processed cannot be deleted.
    """
    firm_uuid = current_user.firm_id
    doc = _get_doc_or_404(db, document_id, firm_uuid)

    if doc.status in {"pending", "uploaded", "processing"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "DOC_006",
                "message": "Cannot delete a document that is currently being processed",
            },
        )

    # Delete from S3
    try:
        s3 = boto3.client("s3", region_name=settings.aws_region)
        s3.delete_object(Bucket=doc.s3_bucket, Key=doc.s3_key)
    except Exception:
        pass  # log but don't block the DB deletion

    doc.pdf_deleted = True
    doc.status = "deleted"

    audit = AuditEvent(
        firm_id=firm_uuid,
        actor_user_id=current_user.user_id,
        action="document.deleted",
        resource_type="document",
        resource_id=str(doc.id),
        metadata={"filename": doc.filename},
    )
    db.add(audit)
    db.commit()

    return {"status": "deleted", "document_id": str(document_id)}
