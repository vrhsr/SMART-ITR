from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.dependencies import get_current_firm
from core.settings import settings
from db import get_db
from models import Firm
from services.invoice import store_invoice_pdf
from services.razorpay_billing import PLAN_AMOUNTS_INR, create_subscription_for_firm, handle_billing_event, verify_webhook_signature

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CreateSubscriptionRequest(BaseModel):
    plan: str


@router.post("/create-subscription")
def create_subscription(
    payload: CreateSubscriptionRequest,
    firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> dict:
    firm: Firm | None = db.scalar(select(Firm).where(Firm.firm_id == firm_id))
    if firm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    return create_subscription_for_firm(db, firm=firm, plan=payload.plan)


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    body = await request.body()
    verify_webhook_signature(body, x_razorpay_signature or "")

    event = json.loads(body.decode("utf-8"))
    payload = event.get("payload", {})
    subscription = payload.get("subscription", {}).get("entity") or {}
    subscription_id = subscription.get("id")

    if not subscription_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing subscription id")

    firm: Firm | None = db.scalar(select(Firm).where(Firm.subscription_id == subscription_id))
    if firm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found for subscription")

    # For captured payments, generate and store GST invoice PDF
    if event.get("event") == "payment.captured":
        plan = firm.subscription_plan or "standard"
        amount_inr = PLAN_AMOUNTS_INR.get(plan, 9999)
        store_invoice_pdf(firm=firm, amount_inr=amount_inr)

    handle_billing_event(db, firm=firm, event=event)

    return {"status": "ok"}


@router.get("/status")
def billing_status(
    firm_id: str = Depends(get_current_firm),
    db: Session = Depends(get_db),
) -> dict:
    firm: Firm | None = db.scalar(select(Firm).where(Firm.firm_id == firm_id))
    if firm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")

    plan = firm.subscription_plan
    amount_inr = PLAN_AMOUNTS_INR.get(plan or "standard", 9999)

    status_value = firm.subscription_status or "inactive"
    next_billing = firm.current_period_end

    return {
        "plan": plan,
        "status": status_value,
        "next_billing_date": next_billing.isoformat() if next_billing else None,
        "amount": amount_inr * 100,
    }

