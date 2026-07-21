"""Add API rate limit buckets.

Revision ID: 20260720_0003
Revises: 20260720_0002
Create Date: 2026-07-20
"""

from __future__ import annotations

from alembic import op

from app.models import ApiRateLimitBucket

revision = "20260720_0003"
down_revision = "20260720_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ApiRateLimitBucket.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    ApiRateLimitBucket.__table__.drop(op.get_bind(), checkfirst=True)
