from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.firm_id", ondelete="RESTRICT"), nullable=False, index=True
    )

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    pan_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    firm = relationship("Firm", back_populates="clients")
    documents = relationship("Document", back_populates="client")

