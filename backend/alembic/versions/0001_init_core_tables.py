"""init core tables

Revision ID: 0001
Revises: None
Create Date: 2026-03-19

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "firms",
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.firm_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_firm_id", "users", ["firm_id"])

    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("pan_last4", sa.String(length=4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.firm_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_clients_firm_id", "clients", ["firm_id"])

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("s3_bucket", sa.String(length=200), nullable=False),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column("kms_key_id", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.firm_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_documents_firm_id", "documents", ["firm_id"])
    op.create_index("ix_documents_client_id", "documents", ["client_id"])
    op.create_index("ix_documents_s3_key", "documents", ["s3_key"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=200), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.firm_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_audit_events_firm_id", "audit_events", ["firm_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_firm_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_documents_s3_key", table_name="documents")
    op.drop_index("ix_documents_client_id", table_name="documents")
    op.drop_index("ix_documents_firm_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_clients_firm_id", table_name="clients")
    op.drop_table("clients")

    op.drop_index("ix_users_firm_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_table("firms")

