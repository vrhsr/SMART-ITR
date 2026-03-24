"""add consent table and pdf flags

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-19

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=False),
        sa.Column("consent_text_version", sa.String(length=50), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("given_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.firm_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_consent_records_firm_id", "consent_records", ["firm_id"])
    op.create_index("ix_consent_records_client_id", "consent_records", ["client_id"])

    op.add_column("clients", sa.Column("last_activity", sa.DateTime(timezone=True), nullable=True))

    op.add_column("documents", sa.Column("pdf_deleted", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("documents", sa.Column("pdf_deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "pdf_deleted_at")
    op.drop_column("documents", "pdf_deleted")
    op.drop_column("clients", "last_activity")

    op.drop_index("ix_consent_records_client_id", table_name="consent_records")
    op.drop_index("ix_consent_records_firm_id", table_name="consent_records")
    op.drop_table("consent_records")

