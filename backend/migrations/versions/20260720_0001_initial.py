"""Initial normalized scheduling schema.

Revision ID: 20260720_0001
Revises: None
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260720_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patients")),
        sa.UniqueConstraint("phone", "date_of_birth", name="uq_patient_identity"),
    )
    op.create_index(op.f("ix_patients_phone"), "patients", ["phone"], unique=False)

    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
        sa.UniqueConstraint("code", name=op.f("uq_locations_code")),
        sa.UniqueConstraint("name", name=op.f("uq_locations_name")),
    )

    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("accepts_new_patients", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_doctors")),
        sa.UniqueConstraint("first_name", "last_name", name="uq_doctor_name"),
    )

    op.create_table(
        "doctor_locations",
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["doctor_id"],
            ["doctors.id"],
            name=op.f("fk_doctor_locations_doctor_id_doctors"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name=op.f("fk_doctor_locations_location_id_locations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("doctor_id", "location_id", name=op.f("pk_doctor_locations")),
    )

    op.create_table(
        "doctor_capabilities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("body_part", sa.String(length=32), nullable=False),
        sa.Column("issue_type", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["doctor_id"],
            ["doctors.id"],
            name=op.f("fk_doctor_capabilities_doctor_id_doctors"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_doctor_capabilities")),
        sa.UniqueConstraint("doctor_id", "body_part", "issue_type", name="uq_doctor_capability"),
    )

    op.create_table(
        "slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["doctor_id"],
            ["doctors.id"],
            name=op.f("fk_slots_doctor_id_doctors"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name=op.f("fk_slots_location_id_locations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_slots")),
        sa.UniqueConstraint("doctor_id", "location_id", "starts_at", name="uq_slot_start"),
    )
    op.create_index("ix_slots_availability", "slots", ["status", "starts_at"], unique=False)

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("body_part", sa.String(length=32), nullable=False),
        sa.Column("issue_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("booking_source", sa.String(length=32), nullable=False),
        sa.Column("call_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["doctor_id"],
            ["doctors.id"],
            name=op.f("fk_appointments_doctor_id_doctors"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name=op.f("fk_appointments_location_id_locations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name=op.f("fk_appointments_patient_id_patients"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["slots.id"],
            name=op.f("fk_appointments_slot_id_slots"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointments")),
        sa.UniqueConstraint("slot_id", name=op.f("uq_appointments_slot_id")),
    )

    op.create_table(
        "patient_doctor_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("most_recent_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointments.id"],
            name=op.f("fk_patient_doctor_history_appointment_id_appointments"),
        ),
        sa.ForeignKeyConstraint(
            ["doctor_id"],
            ["doctors.id"],
            name=op.f("fk_patient_doctor_history_doctor_id_doctors"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name=op.f("fk_patient_doctor_history_patient_id_patients"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patient_doctor_history")),
        sa.UniqueConstraint("patient_id", "doctor_id", name="uq_patient_doctor_history"),
    )

    op.create_table(
        "calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_call_id", sa.String(length=128), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("caller_phone", sa.String(length=32), nullable=False),
        sa.Column("patient_status", sa.String(length=16), nullable=True),
        sa.Column("requested_body_part", sa.String(length=32), nullable=True),
        sa.Column("requested_issue_type", sa.String(length=32), nullable=True),
        sa.Column("preferred_doctor_id", sa.Integer(), nullable=True),
        sa.Column("preferred_location_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transcript", sa.JSON(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("redirect_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointments.id"],
            name=op.f("fk_calls_appointment_id_appointments"),
        ),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], name=op.f("fk_calls_patient_id_patients")),
        sa.ForeignKeyConstraint(
            ["preferred_doctor_id"],
            ["doctors.id"],
            name=op.f("fk_calls_preferred_doctor_id_doctors"),
        ),
        sa.ForeignKeyConstraint(
            ["preferred_location_id"],
            ["locations.id"],
            name=op.f("fk_calls_preferred_location_id_locations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calls")),
        sa.UniqueConstraint("external_call_id", name=op.f("uq_calls_external_call_id")),
    )

    op.create_table(
        "transcript_turns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("call_id", sa.Integer(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["call_id"],
            ["calls.id"],
            name=op.f("fk_transcript_turns_call_id_calls"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transcript_turns")),
        sa.UniqueConstraint("call_id", "sequence_number", name="uq_call_turn"),
    )

    op.create_table(
        "routing_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("call_id", sa.Integer(), nullable=True),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("doctor_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("human_readable_reason", sa.Text(), nullable=False),
        sa.Column("request_context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["call_id"],
            ["calls.id"],
            name=op.f("fk_routing_decisions_call_id_calls"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], name=op.f("fk_routing_decisions_doctor_id_doctors")),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], name=op.f("fk_routing_decisions_patient_id_patients")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_routing_decisions")),
    )


def downgrade() -> None:
    op.drop_table("routing_decisions")
    op.drop_table("transcript_turns")
    op.drop_table("calls")
    op.drop_table("patient_doctor_history")
    op.drop_table("appointments")
    op.drop_index("ix_slots_availability", table_name="slots")
    op.drop_table("slots")
    op.drop_table("doctor_capabilities")
    op.drop_table("doctor_locations")
    op.drop_table("doctors")
    op.drop_table("locations")
    op.drop_index(op.f("ix_patients_phone"), table_name="patients")
    op.drop_table("patients")
