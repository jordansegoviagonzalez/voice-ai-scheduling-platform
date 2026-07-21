from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("phone", "date_of_birth", name="uq_patient_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255))

    appointments: Mapped[list[Appointment]] = relationship(back_populates="patient")
    doctor_history: Mapped[list[PatientDoctorHistory]] = relationship(back_populates="patient")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    doctors: Mapped[list[Doctor]] = relationship(secondary="doctor_locations", back_populates="locations")


class Doctor(Base, TimestampMixin):
    __tablename__ = "doctors"
    __table_args__ = (UniqueConstraint("first_name", "last_name", name="uq_doctor_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    accepts_new_patients: Mapped[bool] = mapped_column(Boolean, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    locations: Mapped[list[Location]] = relationship(secondary="doctor_locations", back_populates="doctors")
    capabilities: Mapped[list[DoctorCapability]] = relationship(back_populates="doctor", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return f"Dr. {self.first_name} {self.last_name}"


class DoctorLocation(Base):
    __tablename__ = "doctor_locations"

    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True)


class DoctorCapability(Base):
    __tablename__ = "doctor_capabilities"
    __table_args__ = (UniqueConstraint("doctor_id", "body_part", "issue_type", name="uq_doctor_capability"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    body_part: Mapped[str] = mapped_column(String(32), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(32), nullable=False)

    doctor: Mapped[Doctor] = relationship(back_populates="capabilities")


class PatientDoctorHistory(Base, TimestampMixin):
    __tablename__ = "patient_doctor_history"
    __table_args__ = (UniqueConstraint("patient_id", "doctor_id", name="uq_patient_doctor_history"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    most_recent_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="seed")
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))

    patient: Mapped[Patient] = relationship(back_populates="doctor_history")
    doctor: Mapped[Doctor] = relationship()


class Slot(Base, TimestampMixin):
    __tablename__ = "slots"
    __table_args__ = (
        UniqueConstraint("doctor_id", "location_id", "starts_at", name="uq_slot_start"),
        Index("ix_slots_availability", "status", "starts_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")

    doctor: Mapped[Doctor] = relationship()
    location: Mapped[Location] = relationship()
    appointment: Mapped[Appointment | None] = relationship(back_populates="slot", uselist=False)


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"))
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id", ondelete="RESTRICT"), unique=True)
    body_part: Mapped[str] = mapped_column(String(32), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="SCHEDULED")
    booking_source: Mapped[str] = mapped_column(String(32), nullable=False, default="WEB")
    call_id: Mapped[int | None] = mapped_column(Integer)

    patient: Mapped[Patient] = relationship(back_populates="appointments")
    doctor: Mapped[Doctor] = relationship()
    location: Mapped[Location] = relationship()
    slot: Mapped[Slot] = relationship(back_populates="appointment")


class BookingConfirmation(Base, TimestampMixin):
    __tablename__ = "booking_confirmations"
    __table_args__ = (
        UniqueConstraint("confirmation_token", name="uq_booking_confirmation_token"),
        Index("ix_booking_confirmations_status_expires", "status", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    confirmation_token: Mapped[str] = mapped_column(String(64), nullable=False)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="RESTRICT"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id", ondelete="RESTRICT"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    body_part: Mapped[str] = mapped_column(String(32), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(32), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="CONFIRMED")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="API")
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id", ondelete="SET NULL"))

    call: Mapped[Call] = relationship(foreign_keys=[call_id])
    patient: Mapped[Patient] = relationship()
    slot: Mapped[Slot] = relationship()
    doctor: Mapped[Doctor] = relationship()
    location: Mapped[Location] = relationship()
    appointment: Mapped[Appointment | None] = relationship()


class IntegrationStatus(Base, TimestampMixin):
    __tablename__ = "integration_statuses"
    __table_args__ = (UniqueConstraint("integration_name", name="uq_integration_status_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class IntegrationRequestLog(Base, TimestampMixin):
    __tablename__ = "integration_request_logs"
    __table_args__ = (
        UniqueConstraint("provider", "operation", "external_id", name="uq_integration_request_external"),
        Index("ix_integration_request_lookup", "provider", "operation", "external_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    external_id: Mapped[str] = mapped_column(String(160), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status_code: Mapped[int | None] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="STARTED")


class IntegrationEventLog(Base, TimestampMixin):
    __tablename__ = "integration_event_logs"
    __table_args__ = (
        UniqueConstraint("provider", "event_key", name="uq_integration_event_key"),
        Index("ix_integration_event_call", "provider", "external_call_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    external_call_id: Mapped[str | None] = mapped_column(String(128))
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RECEIVED")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiRateLimitBucket(Base, TimestampMixin):
    __tablename__ = "api_rate_limit_buckets"
    __table_args__ = (
        UniqueConstraint("bucket_key", name="uq_api_rate_limit_bucket_key"),
        Index("ix_api_rate_limit_route_window", "route", "window_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bucket_key: Mapped[str] = mapped_column(String(220), nullable=False)
    route: Mapped[str] = mapped_column(String(120), nullable=False)
    identifier_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Call(Base, TimestampMixin):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_call_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="IN_PROGRESS")
    caller_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    patient_status: Mapped[str | None] = mapped_column(String(16))
    requested_body_part: Mapped[str | None] = mapped_column(String(32))
    requested_issue_type: Mapped[str | None] = mapped_column(String(32))
    preferred_doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    preferred_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    redirect_summary: Mapped[str | None] = mapped_column(Text)

    patient: Mapped[Patient | None] = relationship()
    preferred_doctor: Mapped[Doctor | None] = relationship(foreign_keys=[preferred_doctor_id])
    preferred_location: Mapped[Location | None] = relationship(foreign_keys=[preferred_location_id])
    appointment: Mapped[Appointment | None] = relationship(foreign_keys=[appointment_id])
    transcript_turns: Mapped[list[TranscriptTurn]] = relationship(
        back_populates="call", cascade="all, delete-orphan", order_by="TranscriptTurn.sequence_number"
    )
    routing_decisions: Mapped[list[RoutingDecision]] = relationship(
        back_populates="call", cascade="all, delete-orphan", order_by="RoutingDecision.created_at"
    )


class TranscriptTurn(Base):
    __tablename__ = "transcript_turns"
    __table_args__ = (UniqueConstraint("call_id", "sequence_number", name="uq_call_turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"))
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    call: Mapped[Call] = relationship(back_populates="transcript_turns")


class RoutingDecision(Base):
    __tablename__ = "routing_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[int | None] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"))
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    human_readable_reason: Mapped[str] = mapped_column(Text, nullable=False)
    request_context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    call: Mapped[Call | None] = relationship(back_populates="routing_decisions")
    doctor: Mapped[Doctor | None] = relationship()
