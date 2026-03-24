"""
Validation Findings endpoints.

GET    /api/v1/ca/clients/{client_id}/findings           — List all findings for a client
POST   /api/v1/ca/findings/{finding_id}/resolve          — CA resolves a finding
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import get_current_firm, get_current_user
from auth.jwt import AuthenticatedUser
from db import get_db
from models import AuditEvent, Client, Document, ValidationFinding
from schemas.base import ErrorCodes

router = APIRouter()


class FindingResponse(BaseModel):
    id: str
    document_id: str
    finding_type: str
    severity: str
    message: str
    details: dict
    resolved: bool
    resolution: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


class ResolveRequest(BaseModel):
    resolution: str
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /api/v1/ca/clients/{client_id}/findings
# ---------------------------------------------------------------------------

@router.get("/clients/{client_id}/findings")
def list_client_findings(
    client_id: uuid.UUID,
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return all validation findings for all documents belonging to a client."""
    firm_uuid = uuid.UUID(current_firm_id)

    # Confirm client belongs to this firm
    client = db.scalar(
        sa.select(Client).where(Client.id == client_id, Client.firm_id == firm_uuid)
    )
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": ErrorCodes.CLIENT_001, "message": "Client not found"},
        )

    # Get all document IDs for this client
    doc_ids = [
        row.id for row in
        db.scalars(sa.select(Document.id).where(Document.client_id == client_id)).all()
    ]

    if not doc_ids:
        return []

    findings = db.scalars(
        sa.select(ValidationFinding)
        .where(
            ValidationFinding.firm_id == firm_uuid,
            ValidationFinding.document_id.in_(doc_ids),
        )
        .order_by(ValidationFinding.created_at.desc())
    ).all()

    return [
        {
            "id": str(f.id),
            "document_id": str(f.document_id),
            "finding_type": f.finding_type,
            "severity": f.severity,
            "message": f.message,
            "details": f.details or {},
            "created_at": f.created_at.isoformat(),
        }
        for f in findings
    ]


# ---------------------------------------------------------------------------
# POST /api/v1/ca/findings/{finding_id}/resolve
# ---------------------------------------------------------------------------

@router.post("/findings/{finding_id}/resolve")
def resolve_finding(
    finding_id: uuid.UUID,
    payload: ResolveRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """CA marks a validation finding as resolved with an explanation."""
    firm_uuid = current_user.firm_id

    finding = db.scalar(
        sa.select(ValidationFinding).where(
            ValidationFinding.id == finding_id,
            ValidationFinding.firm_id == firm_uuid,
        )
    )
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FINDING_001", "message": "Finding not found"},
        )

    # Store resolution in details dict
    details = dict(finding.details or {})
    details["resolved"] = True
    details["resolution"] = payload.resolution
    details["resolution_note"] = payload.note
    finding.details = details

    audit = AuditEvent(
        firm_id=firm_uuid,
        actor_user_id=current_user.user_id,
        action="finding.resolved",
        resource_type="validation_finding",
        resource_id=str(finding.id),
        metadata={"resolution": payload.resolution},
    )
    db.add(audit)
    db.commit()

    return {"status": "resolved", "finding_id": str(finding_id)}
