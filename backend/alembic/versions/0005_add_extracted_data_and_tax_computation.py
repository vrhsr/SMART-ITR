"""add extracted_data and tax_computation columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-19

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Adding JSONB to documents
    op.add_column("documents", sa.Column("extracted_data", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("tax_computation", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "extracted_data")
    op.drop_column("documents", "tax_computation")
