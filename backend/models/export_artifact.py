from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class ExportArtifact(Base, TimestampMixin):
    __tablename__ = "export_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.firm_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)  # itdx_json, excel, client_report_pdf
    s3_bucket: Mapped[str] = mapped_column(String(200), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    generated_by: Mapped[str | None] = mapped_column(String(50), nullable=True)  # pipeline | manual

