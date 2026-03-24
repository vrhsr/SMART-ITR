"""add firm branding

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-19

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("firms", sa.Column("logo_s3_key", sa.String(length=1024), nullable=True))
    op.add_column("firms", sa.Column("brand_primary_color", sa.String(length=7), nullable=True))
    op.add_column("firms", sa.Column("subdomain", sa.String(length=100), nullable=True))
    op.create_unique_constraint("uq_firms_subdomain", "firms", ["subdomain"])


def downgrade() -> None:
    op.drop_constraint("uq_firms_subdomain", "firms", type_="unique")
    op.drop_column("firms", "subdomain")
    op.drop_column("firms", "brand_primary_color")
    op.drop_column("firms", "logo_s3_key")
