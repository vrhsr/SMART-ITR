from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class UploadToken(Base, TimestampMixin):
    """
    Secure, time-limited, client-scoped tokens for the white-label
    client upload portal. A CA generates one of these per client;
    the resulting URL lets a taxpayer upload their documents without
    requiring an account or login.

    Token lifecycle:
      ACTIVE → USED (all uploads done) | EXPIRED (TTL passed) | REVOKED
    """

    __tablename__ = "upload_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("firms.firm_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # The token string stored as a SHA-256 hash for security.
    # The plaintext is only returned to the CA once on creation.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_uploads: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    uploads_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # allowed_doc_types: comma-separated e.g. "form16,ais,26as"
    allowed_doc_types: Mapped[str | None] = mapped_column(String(200), nullable=True)

    firm = relationship("Firm")
    client = relationship("Client")
