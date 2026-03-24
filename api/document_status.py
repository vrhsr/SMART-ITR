from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db import get_db
from models import Document
from auth.dependencies import get_current_firm

router = APIRouter(prefix="/api/documents", tags=["document-status"])


@router.get("/{document_id}/status")
def get_document_status(
    document_id: uuid.UUID,
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get real-time processing status of a document through the pipeline.
    The frontend can poll this every few seconds to show a live progress bar.
    """
    firm_uuid = uuid.UUID(current_firm_id)

    doc = db.scalar(
        sa.select(Document).where(
            Document.id == document_id,
            Document.firm_id == firm_uuid,
        )
    )
    if not doc:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Map internal status to user-friendly pipeline steps
    PIPELINE_STEPS = {
        "pending":           {"step": 0, "total": 5, "label": "Waiting to process…"},
        "uploaded":          {"step": 1, "total": 5, "label": "Document received"},
        "processing":        {"step": 2, "total": 5, "label": "Classifying document…"},
        "classified":        {"step": 2, "total": 5, "label": "Document type identified"},
        "extracted":         {"step": 3, "total": 5, "label": "Fields extracted via AI"},
        "validated":         {"step": 4, "total": 5, "label": "Cross-document validation done"},
        "ready_for_review":  {"step": 5, "total": 5, "label": "Ready for CA review ✓"},
        "approved":          {"step": 5, "total": 5, "label": "Approved by CA ✓"},
        "error":             {"step": 0, "total": 5, "label": "Processing error — manual review required"},
    }

    pipeline_info = PIPELINE_STEPS.get(
        doc.status or "pending",
        {"step": 0, "total": 5, "label": "Unknown status"}
    )

    return {
        "document_id": str(doc.id),
        "filename": doc.filename,
        "document_type": doc.document_type,
        "status": doc.status,
        "pipeline": pipeline_info,
        "extracted_data": doc.extracted_data,
        "tax_computation": doc.tax_computation,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }
