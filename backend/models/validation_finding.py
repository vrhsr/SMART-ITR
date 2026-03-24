from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class ValidationFinding(Base, TimestampMixin):
    __tablename__ = "validation_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.firm_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    finding_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

