from __future__ import annotations

from datetime import datetime, timedelta, timezone

import boto3
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.settings import settings
from models import AuditEvent, Client, Document


def run_auto_delete_pdfs(db: Session) -> None:
    """
    Daily job:
    - Find Documents where status='approved' AND pdf_deleted=False
    - Delete raw PDF from S3
    - Update flags and create AuditEvent
    """

    s3 = boto3.client("s3", region_name=settings.aws_region)
    docs = list(
        db.scalars(
            select(Document).where(
                Document.status == "approved",
                Document.pdf_deleted.is_(False),
            )
        )
    )
    now = datetime.now(timezone.utc)
    for d in docs:
        try:
            s3.delete_object(Bucket=d.s3_bucket, Key=d.s3_key)
        except Exception:
            continue
        d.pdf_deleted = True
        d.pdf_deleted_at = now
        db.add(d)
        audit = AuditEvent(
            firm_id=d.firm_id,
            actor_user_id=None,
            action="pdf_deleted",
            resource_type="document",
            resource_id=str(d.id),
            details={},
        )
        db.add(audit)
    db.commit()


def run_data_retention_purge(db: Session, *, months: int = 12) -> None:
    """
    Monthly job:
    - Find clients with last_activity older than retention window.
    - For now, purge immediately (notice flow can be added when email infra exists).
    """

    cutoff = datetime.now(timezone.utc) - timedelta(days=30 * months)
    stale_clients = list(db.scalars(select(Client).where(Client.last_activity.is_not(None), Client.last_activity < cutoff)))

    for client in stale_clients:
        docs = list(
            db.scalars(select(Document).where(Document.client_id == client.id, Document.firm_id == client.firm_id))
        )
        for d in docs:
            db.delete(d)
        audit = AuditEvent(
            firm_id=client.firm_id,
            actor_user_id=None,
            action="data_purged",
            resource_type="client",
            resource_id=str(client.id),
            details={"reason": "retention_period_expired"},
        )
        db.add(audit)
        db.delete(client)

    db.commit()

