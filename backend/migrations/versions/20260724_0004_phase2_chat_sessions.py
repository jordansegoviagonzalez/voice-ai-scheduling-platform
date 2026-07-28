"""Add Phase 2 chat session tables.

Revision ID: 20260724_0004
Revises: 20260720_0003
Create Date: 2026-07-24
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text

revision = "20260724_0004"
down_revision = "20260720_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        Column("id", Integer, primary_key=True),
        Column("patient_id", Integer, ForeignKey("patients.id"), nullable=True),
        Column("status", String(32), nullable=False, default="active"),
        Column("current_step", String(64), nullable=False, default="patient_access"),
        Column("collected_data_json", JSON, nullable=False),
        Column("routing_result_json", JSON, nullable=True),
        Column("appointment_id", Integer, ForeignKey("appointments.id"), nullable=True),
        Column("escalation_type", String(32), nullable=True),
        Column("escalation_reason", Text, nullable=True),
        Column("escalation_trigger_message_id", Integer, nullable=True),
        Column("completed_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "chat_messages",
        Column("id", Integer, primary_key=True),
        Column("session_id", Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        Column("role", String(16), nullable=False),
        Column("content", Text, nullable=False),
        Column("sequence_number", Integer, nullable=False),
        Column("metadata_json", JSON, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "chat_session_events",
        Column("id", Integer, primary_key=True),
        Column("session_id", Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        Column("event_type", String(64), nullable=False),
        Column("event_data_json", JSON, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )

    op.create_foreign_key(
        "fk_chat_sessions_escalation_trigger_message_id",
        "chat_sessions",
        "chat_messages",
        ["escalation_trigger_message_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_chat_sessions_escalation_trigger_message_id", "chat_sessions", type_="foreignkey")
    op.drop_table("chat_session_events")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
