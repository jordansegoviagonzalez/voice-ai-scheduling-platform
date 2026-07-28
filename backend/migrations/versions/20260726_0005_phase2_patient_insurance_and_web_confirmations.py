"""Add Phase 2 patient insurance and web confirmation support.

Revision ID: 20260726_0005
Revises: 20260724_0004
Create Date: 2026-07-26
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import Column, Integer, String

revision = "20260726_0005"
down_revision = "20260724_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", Column("insurance_provider", String(255), nullable=True))
    op.alter_column("booking_confirmations", "call_id", existing_type=Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("booking_confirmations", "call_id", existing_type=Integer(), nullable=False)
    op.drop_column("patients", "insurance_provider")
