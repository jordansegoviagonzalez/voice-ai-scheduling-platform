"""Add pre-live integration and confirmation tables.

Revision ID: 20260720_0002
Revises: 20260720_0001
Create Date: 2026-07-20
"""

from __future__ import annotations

from alembic import op

from app.models import BookingConfirmation, IntegrationEventLog, IntegrationRequestLog, IntegrationStatus

revision = "20260720_0002"
down_revision = "20260720_0001"
branch_labels = None
depends_on = None


TABLES = (
    BookingConfirmation.__table__,
    IntegrationStatus.__table__,
    IntegrationRequestLog.__table__,
    IntegrationEventLog.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind, checkfirst=True)
