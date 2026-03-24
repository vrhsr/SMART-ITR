"""
Tax computation endpoints — the product's core value.

GET  /api/v1/ca/clients/{client_id}/tax           — View regime comparison
POST /api/v1/ca/clients/{client_id}/tax/recompute — Recalculate after CA field overrides

These endpoints call the deterministic engine/tax_calculator.py — NO AI involved.
All amounts are returned in BOTH paise (exact integer) and rupees (float, for display).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.dependencies import get_current_firm, get_current_user
from auth.jwt import AuthenticatedUser
from db import get_db
from engine.tax_calculator import compare_regimes
from models import AuditEvent, Client, Document
from schemas.base import ErrorCodes

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class RegimeDetail(BaseModel):
    total_tax_paise: int
    total_tax_rupees: float
    tax_before_cess_paise: int
    surcharge_paise: int
    cess_paise: int


class TaxComputationResponse(BaseModel):
    client_id: str
    document_id: Optional[str]            # which doc's extracted_data was used
    old_regime: RegimeDetail
    new_regime: RegimeDetail
    recommended_regime: str               # "old" | "new"
    savings_paise: int
    savings_rupees: float
    savings_percentage_bps: int           # basis points (÷100 for %)
    deductions_applied: dict
    income_inputs: dict                    # echoes what was used (no PAN/Aadhaar)
    computed_at: str


def _rupees(paise: int) -> float:
    return round(paise / 100, 2)


def _build_income_data_from_docs(docs: list[Document]) -> dict[str, Any]:
    """
    Aggregate extracted_data from all client documents into a single income_data dict.
    Sums up gross income and deductions.
    """
    total_gross_paise = 0
    total_80c_paise = 0
    is_salaried = False
    age_years = 30
    
    for doc in docs:
        extracted = doc.extracted_data or {}
        gross_paise = int(
            extracted.get("total_income_paise")
            or extracted.get("gross_income_paise")
            or (extracted.get("gross_salary_rupees", 0) * 100)
            or 0
        )
        total_gross_paise += gross_paise
        total_80c_paise += int(extracted.get("deductions", {}).get("80C_paise", 0))
        
        if extracted.get("is_salaried"):
            is_salaried = True
        
        if int(extracted.get("age_years", 0)) > 30:
            age_years = max(age_years, int(extracted.get("age_years", 30)))

    return {
        "total_income_paise": total_gross_paise,
        "is_salaried": is_salaried,
        "age_years": age_years,
        "deductions": {
            "80C_paise": total_80c_paise,
        },
    }


def _fetch_all_processed_docs(db: Session, client_id: uuid.UUID, firm_id: uuid.UUID) -> list[Document]:
    """Return all approved or processed documents for a client."""
    docs = db.scalars(
        sa.select(Document).where(
            Document.client_id == client_id,
            Document.firm_id == firm_id,
            Document.status.in_(["approved", "ready_for_review"]),
            Document.extracted_data.isnot(None),
        ).order_by(Document.updated_at.desc())
    ).all()
    if not docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCodes.DOC_005,
                "message": "No processed documents found for this client. "
                           "Upload and process at least one document first.",
            },
        )
    return list(docs)


# ---------------------------------------------------------------------------
# GET /api/v1/ca/clients/{client_id}/tax
# ---------------------------------------------------------------------------

@router.get("/clients/{client_id}/tax", response_model=TaxComputationResponse)
def get_tax_computation(
    client_id: uuid.UUID,
    current_firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> TaxComputationResponse:
    """
    Return the regime comparison for a client using their latest processed document.

    If the document has a cached tax_computation from the pipeline, that is returned
    directly. Otherwise, it is computed on-the-fly from extracted_data.
    """
    firm_uuid = uuid.UUID(current_firm_id)

    # Verify client belongs to firm
    client = db.scalar(
        sa.select(Client).where(Client.id == client_id, Client.firm_id == firm_uuid)
    )
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": ErrorCodes.CLIENT_001, "message": "Client not found"},
        )

    doc_list = _fetch_all_processed_docs(db, client_id, firm_uuid)
    latest_doc = doc_list[0]

    # Use cached result from pipeline on the latest doc if available
    cached = latest_doc.tax_computation
    if cached and "old_tax" in cached:
        result = cached
    else:
        income_data = _build_income_data_from_docs(doc_list)
        result = compare_regimes(income_data)
        latest_doc.tax_computation = result
        db.add(latest_doc)
        db.commit()

    old_tax = result["old_tax"]
    new_tax = result["new_tax"]

    # compare_regimes returns old/new without breakdown — compute cess/surcharge
    # for display. For now we surface them from the old-regime calculator.
    from engine.tax_calculator import calculate_old_regime_tax, calculate_new_regime_tax  # noqa: PLC0415
    income_data = _build_income_data_from_docs(doc_list)
    old_detail = calculate_old_regime_tax(income_data)
    new_detail = calculate_new_regime_tax(income_data["total_income_paise"])

    return TaxComputationResponse(
        client_id=str(client_id),
        document_id=str(latest_doc.id),
        old_regime=RegimeDetail(
            total_tax_paise=old_detail["total_tax"],
            total_tax_rupees=_rupees(old_detail["total_tax"]),
            tax_before_cess_paise=old_detail["tax_before_cess"],
            surcharge_paise=old_detail["surcharge"],
            cess_paise=old_detail["cess"],
        ),
        new_regime=RegimeDetail(
            total_tax_paise=new_detail["total_tax"],
            total_tax_rupees=_rupees(new_detail["total_tax"]),
            tax_before_cess_paise=new_detail["tax_before_cess"],
            surcharge_paise=new_detail["surcharge"],
            cess_paise=new_detail["cess"],
        ),
        recommended_regime=result["recommended_regime"],
        savings_paise=result["savings"],
        savings_rupees=_rupees(result["savings"]),
        savings_percentage_bps=result["savings_percentage"],
        deductions_applied=result.get("deductions_applied", {}),
        income_inputs={
            "total_income_rupees": income_data["total_income_paise"] // 100,
            "is_salaried": income_data["is_salaried"],
            "age_years": income_data["age_years"],
        },
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/ca/clients/{client_id}/tax/recompute
# ---------------------------------------------------------------------------

@router.post("/clients/{client_id}/tax/recompute", response_model=TaxComputationResponse)
def recompute_tax(
    client_id: uuid.UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaxComputationResponse:
    """
    Force recalculation of tax after a CA has overridden extracted fields.

    Deterministic: same inputs → same outputs. No AI, no network calls.
    Saves the result back to document.tax_computation (overwrites cache).
    Creates an audit event.
    """
    firm_uuid = current_user.firm_id

    client = db.scalar(
        sa.select(Client).where(Client.id == client_id, Client.firm_id == firm_uuid)
    )
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": ErrorCodes.CLIENT_001, "message": "Client not found"},
        )

    doc_list = _fetch_all_processed_docs(db, client_id, firm_uuid)
    latest_doc = doc_list[0]
    income_data = _build_income_data_from_docs(doc_list)
    result = compare_regimes(income_data)

    # Persist the aggregate result back to the latest document
    latest_doc.tax_computation = result
    db.add(latest_doc)

    audit = AuditEvent(
        firm_id=firm_uuid,
        actor_user_id=current_user.user_id,
        action="tax_recomputed",
        resource_type="client",
        resource_id=str(client_id),
        details={
            "recommended": result["recommended_regime"],
            "savings_rupees": _rupees(result["savings"]),
            "total_income_rupees": income_data["total_income_paise"] // 100,
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(latest_doc)

    from engine.tax_calculator import calculate_old_regime_tax, calculate_new_regime_tax  # noqa: PLC0415
    old_detail = calculate_old_regime_tax(income_data)
    new_detail = calculate_new_regime_tax(income_data["total_income_paise"])

    return TaxComputationResponse(
        client_id=str(client_id),
        document_id=str(latest_doc.id),
        old_regime=RegimeDetail(
            total_tax_paise=old_detail["total_tax"],
            total_tax_rupees=_rupees(old_detail["total_tax"]),
            tax_before_cess_paise=old_detail["tax_before_cess"],
            surcharge_paise=old_detail["surcharge"],
            cess_paise=old_detail["cess"],
        ),
        new_regime=RegimeDetail(
            total_tax_paise=new_detail["total_tax"],
            total_tax_rupees=_rupees(new_detail["total_tax"]),
            tax_before_cess_paise=new_detail["tax_before_cess"],
            surcharge_paise=new_detail["surcharge"],
            cess_paise=new_detail["cess"],
        ),
        recommended_regime=result["recommended_regime"],
        savings_paise=result["savings"],
        savings_rupees=_rupees(result["savings"]),
        savings_percentage_bps=result["savings_percentage"],
        deductions_applied=result.get("deductions_applied", {}),
        income_inputs={
            "total_income_rupees": income_data["total_income_paise"] // 100,
            "is_salaried": income_data["is_salaried"],
            "age_years": income_data["age_years"],
        },
        computed_at=datetime.now(timezone.utc).isoformat(),
    )
