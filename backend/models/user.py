from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin
from models.enums import UserRole


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("firms.firm_id", ondelete="RESTRICT"), nullable=False, index=True
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[UserRole] = mapped_column(nullable=False, default=UserRole.staff)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    firm = relationship("Firm", back_populates="users")

