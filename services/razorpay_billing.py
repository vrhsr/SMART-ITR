from __future__ import annotations

import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import razorpay
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.settings import settings
from models import AuditEvent, Firm


PLAN_AMOUNTS_INR = {
    "pilot": 5000,
    "standard": 9999,
    "growth": 19999,
}


def _client() -> razorpay.Client:
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def create_subscription_for_firm(db: Session, *, firm: Firm, plan: str) -> dict[str, Any]:
    if plan not in PLAN_AMOUNTS_INR:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown plan")

    client = _client()
    amount_in_paise = PLAN_AMOUNTS_INR[plan] * 100

    subscription = client.subscription.create(
        {
            "plan_id": plan,  # you may map to Razorpay plan IDs externally
            "total_count": 999,
            "quantity": 1,
            "customer_notify": 1,
        }
    )

    firm.subscription_plan = plan
    firm.subscription_id = subscription.get("id")
    firm.subscription_status = "trialing"
    now = datetime.now(timezone.utc)
    firm.trial_ends_at = now + timedelta(days=30)
    firm.current_period_end = firm.trial_ends_at
    db.add(firm)
    db.commit()
    db.refresh(firm)

    return {
        "subscription_id": firm.subscription_id,
        "plan": firm.subscription_plan,
        "status": firm.subscription_status,
        "trial_ends_at": firm.trial_ends_at.isoformat() if firm.trial_ends_at else None,
        "amount_paise": amount_in_paise,
    }


def verify_webhook_signature(body: bytes, received_signature: str) -> None:
    """Verify Razorpay webhook signature using HMAC-SHA256."""
    if not received_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing webhook signature header",
        )
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, received_signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )


def _extend_access(firm: Firm) -> None:
    now = datetime.now(timezone.utc)
    base = firm.current_period_end or now
    if base < now:
        base = now
    firm.current_period_end = base + timedelta(days=30)
    firm.subscription_status = "active"
    firm.billing_warning = False


def handle_billing_event(db: Session, *, firm: Firm, event: dict[str, Any]) -> None:
    event_type = event.get("event")
    payload = event.get("payload", {})

    if event_type == "payment.captured":
        _extend_access(firm)
    elif event_type == "payment.failed":
        firm.billing_warning = True
    elif event_type == "subscription.cancelled":
        firm.subscription_status = "cancelled"
        firm.cancellation_date = datetime.now(timezone.utc)

    db.add(firm)

    audit = AuditEvent(
        firm_id=firm.firm_id,
        actor_user_id=None,
        action="billing_event",
        resource_type="subscription",
        resource_id=firm.subscription_id or "",
        details={"event_type": event_type, "payload": payload},
    )
    db.add(audit)
    db.commit()

