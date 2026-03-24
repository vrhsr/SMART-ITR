"""add billing fields to firm

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-19

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("firms", sa.Column("subscription_plan", sa.String(length=50), nullable=True))
  op.add_column("firms", sa.Column("subscription_id", sa.String(length=100), nullable=True))
  op.add_column("firms", sa.Column("subscription_status", sa.String(length=50), nullable=True))
  op.add_column("firms", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
  op.add_column("firms", sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True))
  op.add_column("firms", sa.Column("cancellation_date", sa.DateTime(timezone=True), nullable=True))
  op.add_column("firms", sa.Column("billing_warning", sa.String(length=200), nullable=True))


def downgrade() -> None:
  op.drop_column("firms", "billing_warning")
  op.drop_column("firms", "cancellation_date")
  op.drop_column("firms", "current_period_end")
  op.drop_column("firms", "trial_ends_at")
  op.drop_column("firms", "subscription_status")
  op.drop_column("firms", "subscription_id")
  op.drop_column("firms", "subscription_plan")

