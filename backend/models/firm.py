from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class Firm(Base, TimestampMixin):
    __tablename__ = "firms"

    firm_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    subscription_plan: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    billing_warning: Mapped[str | None] = mapped_column(String(200), nullable=True)

    logo_s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    brand_primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    subdomain: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)

    users = relationship("User", back_populates="firm")
    clients = relationship("Client", back_populates="firm")
    documents = relationship("Document", back_populates="firm")
    audit_events = relationship("AuditEvent", back_populates="firm")
