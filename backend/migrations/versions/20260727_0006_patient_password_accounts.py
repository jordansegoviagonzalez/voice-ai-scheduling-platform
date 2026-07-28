"""Add patient password account fields.

Revision ID: 20260727_0006
Revises: 20260726_0005
Create Date: 2026-07-27
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import Column, String

revision = "20260727_0006"
down_revision = "20260726_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patients", Column("password_hash", String(255), nullable=True))
    op.create_index("ix_patients_email_unique", "patients", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_patients_email_unique", table_name="patients")
    op.drop_column("patients", "password_hash")
