from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import sqlalchemy as sa

from models.base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.firm_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    tax_computation: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    pdf_deleted: Mapped[bool] = mapped_column(nullable=False, default=False)
    pdf_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    s3_bucket: Mapped[str] = mapped_column(String(200), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    kms_key_id: Mapped[str | None] = mapped_column(String(300), nullable=True)

    firm = relationship("Firm", back_populates="documents")
    client = relationship("Client", back_populates="documents")

