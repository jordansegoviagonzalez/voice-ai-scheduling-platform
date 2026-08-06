"""Add multi-organization foundation columns.

Revision ID: 20260805_0007
Revises: 20260727_0006
Create Date: 2026-08-05
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "20260805_0007"
down_revision = "20260727_0006"
branch_labels = None
depends_on = None

DEFAULT_ORGANIZATION_SLUG = "default-orthopedics"
DEFAULT_ORGANIZATION_NAME = "Default Orthopedics"
DEFAULT_ORGANIZATION_TIMEZONE = "America/Los_Angeles"

ORG_SCOPED_TABLES = (
    "locations",
    "doctors",
    "slots",
    "appointments",
    "calls",
    "routing_decisions",
    "chat_sessions",
)


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    bind = op.get_bind()
    now = datetime.now(UTC)
    bind.execute(
        sa.text(
            """
            INSERT INTO organizations (slug, name, status, timezone, created_at, updated_at)
            VALUES (:slug, :name, 'ACTIVE', :timezone, :created_at, :updated_at)
            ON CONFLICT (slug) DO NOTHING
            """
        ),
        {
            "slug": DEFAULT_ORGANIZATION_SLUG,
            "name": DEFAULT_ORGANIZATION_NAME,
            "timezone": DEFAULT_ORGANIZATION_TIMEZONE,
            "created_at": now,
            "updated_at": now,
        },
    )
    default_org_id = bind.execute(
        sa.text("SELECT id FROM organizations WHERE slug = :slug"), {"slug": DEFAULT_ORGANIZATION_SLUG}
    ).scalar_one()

    for table_name in ORG_SCOPED_TABLES:
        op.add_column(table_name, sa.Column("organization_id", sa.Integer(), nullable=True))
        bind.execute(
            sa.text(f"UPDATE {table_name} SET organization_id = :organization_id WHERE organization_id IS NULL"),
            {"organization_id": default_org_id},
        )
        op.alter_column(table_name, "organization_id", existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(
            f"fk_{table_name}_organization_id_organizations",
            table_name,
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    op.drop_constraint("uq_locations_code", "locations", type_="unique")
    op.drop_constraint("uq_locations_name", "locations", type_="unique")
    op.create_unique_constraint("uq_location_org_code", "locations", ["organization_id", "code"])
    op.create_unique_constraint("uq_location_org_name", "locations", ["organization_id", "name"])
    op.create_index("ix_locations_org_code", "locations", ["organization_id", "code"], unique=False)

    op.drop_constraint("uq_doctor_name", "doctors", type_="unique")
    op.create_unique_constraint("uq_doctor_org_name", "doctors", ["organization_id", "first_name", "last_name"])
    op.create_index("ix_doctors_org_active", "doctors", ["organization_id", "active"], unique=False)

    op.drop_constraint("uq_slot_start", "slots", type_="unique")
    op.create_unique_constraint(
        "uq_slot_org_start",
        "slots",
        ["organization_id", "doctor_id", "location_id", "starts_at"],
    )
    op.create_index("ix_slots_org_availability", "slots", ["organization_id", "status", "starts_at"], unique=False)

    op.create_index("ix_appointments_org_status", "appointments", ["organization_id", "status"], unique=False)
    op.create_index("ix_calls_org_started", "calls", ["organization_id", "started_at"], unique=False)
    op.create_index(
        "ix_routing_decisions_org_created",
        "routing_decisions",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_chat_sessions_org_status", "chat_sessions", ["organization_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_org_status", table_name="chat_sessions")
    op.drop_index("ix_routing_decisions_org_created", table_name="routing_decisions")
    op.drop_index("ix_calls_org_started", table_name="calls")
    op.drop_index("ix_appointments_org_status", table_name="appointments")

    op.drop_index("ix_slots_org_availability", table_name="slots")
    op.drop_constraint("uq_slot_org_start", "slots", type_="unique")
    op.create_unique_constraint("uq_slot_start", "slots", ["doctor_id", "location_id", "starts_at"])

    op.drop_index("ix_doctors_org_active", table_name="doctors")
    op.drop_constraint("uq_doctor_org_name", "doctors", type_="unique")
    op.create_unique_constraint("uq_doctor_name", "doctors", ["first_name", "last_name"])

    op.drop_index("ix_locations_org_code", table_name="locations")
    op.drop_constraint("uq_location_org_name", "locations", type_="unique")
    op.drop_constraint("uq_location_org_code", "locations", type_="unique")
    op.create_unique_constraint("uq_locations_name", "locations", ["name"])
    op.create_unique_constraint("uq_locations_code", "locations", ["code"])

    for table_name in reversed(ORG_SCOPED_TABLES):
        op.drop_constraint(f"fk_{table_name}_organization_id_organizations", table_name, type_="foreignkey")
        op.drop_column(table_name, "organization_id")

    op.drop_table("organizations")
