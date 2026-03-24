"""add findings and export artifacts

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-19

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "validation_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.firm_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_validation_findings_firm_id", "validation_findings", ["firm_id"])
    op.create_index("ix_validation_findings_document_id", "validation_findings", ["document_id"])
    op.create_index("ix_validation_findings_finding_type", "validation_findings", ["finding_type"])

    op.create_table(
        "export_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_type", sa.String(length=50), nullable=False),
        sa.Column("s3_bucket", sa.String(length=200), nullable=False),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.firm_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_export_artifacts_firm_id", "export_artifacts", ["firm_id"])
    op.create_index("ix_export_artifacts_document_id", "export_artifacts", ["document_id"])
    op.create_index("ix_export_artifacts_s3_key", "export_artifacts", ["s3_key"])


def downgrade() -> None:
    op.drop_index("ix_export_artifacts_s3_key", table_name="export_artifacts")
    op.drop_index("ix_export_artifacts_document_id", table_name="export_artifacts")
    op.drop_index("ix_export_artifacts_firm_id", table_name="export_artifacts")
    op.drop_table("export_artifacts")

    op.drop_index("ix_validation_findings_finding_type", table_name="validation_findings")
    op.drop_index("ix_validation_findings_document_id", table_name="validation_findings")
    op.drop_index("ix_validation_findings_firm_id", table_name="validation_findings")
    op.drop_table("validation_findings")

