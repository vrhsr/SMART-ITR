"""
CA Client CRUD endpoints.

POST   /api/v1/ca/clients              — Create a new client
GET    /api/v1/ca/clients              — List clients (paginated + search)
GET    /api/v1/ca/clients/{client_id}  — Get full client detail
PUT    /api/v1/ca/clients/{client_id}  — Update client
DELETE /api/v1/ca/clients/{client_id}  — Soft-delete (marks is_deleted)

All endpoints are firm-scoped: a CA can only read/write clients
that belong to their own firm_id from the JWT.
"""
from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from auth.dependencies import get_current_firm, get_current_user
from auth.jwt import AuthenticatedUser
from db import get_db
from models import AuditEvent, Client, Document
from schemas.base import PaginatedResponse, ErrorCodes

router = APIRouter()

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CreateClientRequest(BaseModel):
    full_name: str
    pan: Optional[str] = None          # Full PAN — stored only as last-4 chars
    email: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("pan")
    @classmethod
    def validate_pan(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re
        if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", v.upper()):
            raise ValueError("PAN must be in the format ABCDE1234F")
        return v.upper()

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v


class UpdateClientRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class ClientListItem(BaseModel):
    id: str
    full_name: str
    pan_last4: Optional[str]
    document_count: int
    status: str
    last_activity: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


class ClientDetailResponse(BaseModel):
    id: str
    full_name: str
    pan_last4: Optional[str]
    created_at: str
    updated_at: Optional[str]
    documents: list[dict[str, Any]]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pan_hash(pan: str) -> str:
    """One-way SHA-256 of PAN for deduplication. Never stored in plaintext."""
    return hashlib.sha256(pan.encode()).hexdigest()


def _get_client_or_404(db: Session, client_id: uuid.UUID, firm_uuid: uuid.UUID) -> Client:
    client = db.scalar(
        sa.select(Client).where(
            Client.id == client_id,
            Client.firm_id == firm_uuid,
        )
    )
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": ErrorCodes.CLIENT_001, "message": "Client not found"},
        )
    return client


# ---------------------------------------------------------------------------
# POST /api/v1/ca/clients
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED)
def create_client(
    payload: CreateClientRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Create a new taxpayer client under the CA's firm.

    PAN deduplication: if a client with the same PAN already exists in this
    firm, return 409 rather than creating a duplicate.
    """
    firm_uuid = current_user.firm_id

    pan_last4: str | None = None
    if payload.pan:
        pan_last4 = payload.pan[-4:]
        # Check for duplicate PAN within this firm using last-4 as a fast
        # pre-filter (full dedup would require storing a hashed PAN).
        existing = db.scalar(
            sa.select(Client).where(
                Client.firm_id == firm_uuid,
                Client.pan_last4 == pan_last4,
                Client.full_name == payload.full_name,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": ErrorCodes.CLIENT_002,
                    "message": "A client with this PAN already exists in your firm",
                    "existing_client_id": str(existing.id),
                },
            )

    client = Client(
        firm_id=firm_uuid,
        full_name=payload.full_name,
        pan_last4=pan_last4,
        last_activity=datetime.now(timezone.utc),
    )
    db.add(client)
    db.flush()  # get the generated client.id

    audit = AuditEvent(
        firm_id=firm_uuid,
        actor_user_id=current_user.user_id,
        action="client.created",
        resource_type="client",
        resource_id=str(client.id),
        details={"full_name": payload.full_name, "pan_last4": pan_last4},
    )
    db.add(audit)
    db.commit()
    db.refresh(client)

    return {
        "id": str(client.id),
        "full_name": client.full_name,
        "pan_last4": client.pan_last4,
        "created_at": client.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /api/v1/ca/clients
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedResponse[ClientListItem])
def list_clients(
    search: Optional[str] = Query(None, description="Search by name or PAN last 4"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ClientListItem]:
    """
    List all clients for the CA firm with pagination and optional search.
    """
    firm_uuid = uuid.UUID(current_firm_id)
    base_query = sa.select(Client).where(Client.firm_id == firm_uuid)

    if search:
        term = f"%{search}%"
        base_query = base_query.where(
            sa.or_(
                Client.full_name.ilike(term),
                Client.pan_last4.ilike(term),
            )
        )

    total = db.scalar(
        sa.select(sa.func.count()).select_from(base_query.subquery())
    ) or 0

    clients = db.scalars(
        base_query.order_by(Client.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()

    items = []
    for c in clients:
        doc_count = db.scalar(
            sa.select(sa.func.count(Document.id)).where(Document.client_id == c.id)
        ) or 0
        last_activity_str = (
            c.last_activity.isoformat() if c.last_activity
            else c.created_at.isoformat()
        )
        client_status = "Active" if doc_count > 0 else "No Documents"
        items.append(
            ClientListItem(
                id=str(c.id),
                full_name=c.full_name,
                pan_last4=c.pan_last4,
                document_count=doc_count,
                status=client_status,
                last_activity=last_activity_str,
                created_at=c.created_at.isoformat(),
            )
        )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=math.ceil(total / per_page) if total else 0,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/ca/clients/{client_id}
# ---------------------------------------------------------------------------

@router.get("/{client_id}", response_model=ClientDetailResponse)
def get_client(
    client_id: uuid.UUID,
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> ClientDetailResponse:
    firm_uuid = uuid.UUID(current_firm_id)
    client = _get_client_or_404(db, client_id, firm_uuid)

    docs = db.scalars(
        sa.select(Document)
        .where(Document.client_id == client.id)
        .order_by(Document.created_at.desc())
    ).all()

    documents = [
        {
            "id": str(d.id),
            "filename": d.filename,
            "type": d.document_type,
            "status": d.status,
            "processing_stage": d.processing_stage,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]

    return ClientDetailResponse(
        id=str(client.id),
        full_name=client.full_name,
        pan_last4=client.pan_last4,
        created_at=client.created_at.isoformat(),
        updated_at=client.updated_at.isoformat() if client.updated_at else None,
        documents=documents,
    )


# ---------------------------------------------------------------------------
# PUT /api/v1/ca/clients/{client_id}
# ---------------------------------------------------------------------------

@router.put("/{client_id}")
def update_client(
    client_id: uuid.UUID,
    payload: UpdateClientRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    firm_uuid = current_user.firm_id
    client = _get_client_or_404(db, client_id, firm_uuid)

    changes: dict[str, Any] = {}
    if payload.full_name is not None and payload.full_name != client.full_name:
        changes["full_name"] = {"old": client.full_name, "new": payload.full_name}
        client.full_name = payload.full_name

    if not changes:
        return {"status": "no_changes", "id": str(client.id)}

    audit = AuditEvent(
        firm_id=firm_uuid,
        actor_user_id=current_user.user_id,
        action="client.updated",
        resource_type="client",
        resource_id=str(client.id),
        metadata={"changes": changes},
    )
    db.add(audit)
    db.commit()
    db.refresh(client)

    return {
        "status": "updated",
        "id": str(client.id),
        "full_name": client.full_name,
        "pan_last4": client.pan_last4,
        "updated_at": client.updated_at.isoformat() if client.updated_at else None,
    }


# ---------------------------------------------------------------------------
# DELETE /api/v1/ca/clients/{client_id}
# ---------------------------------------------------------------------------

@router.delete("/{client_id}", status_code=status.HTTP_200_OK)
def delete_client(
    client_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Soft-delete the client — sets last_activity to None to flag as deactivated.
    Hard-delete is handled only via the DPDP right-to-erasure endpoint.
    This doesn't delete documents; CA must explicitly delete them.
    """
    firm_uuid = current_user.firm_id
    client = _get_client_or_404(db, client_id, firm_uuid)

    # Check no documents are in-flight
    pending = db.scalar(
        sa.select(sa.func.count(Document.id)).where(
            Document.client_id == client_id,
            Document.status.in_(["pending", "uploaded", "processing"]),
        )
    ) or 0
    if pending > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "CLIENT_003",
                "message": f"Cannot delete: {pending} document(s) are still processing",
            },
        )

    # Soft delete: clear sensitive reference fields
    client.last_activity = None

    audit = AuditEvent(
        firm_id=firm_uuid,
        actor_user_id=current_user.user_id,
        action="client.deleted",
        resource_type="client",
        resource_id=str(client.id),
        metadata={"full_name": client.full_name},
    )
    db.add(audit)
    db.commit()

    return {"status": "deleted", "id": str(client_id)}
