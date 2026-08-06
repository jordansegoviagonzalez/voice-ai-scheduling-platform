from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.entities import Appointment, Organization, Patient


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"
    __table_args__ = (Index("ix_chat_sessions_org_status", "organization_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    current_step: Mapped[str] = mapped_column(String(64), nullable=False, default="patient_access")
    collected_data_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    routing_result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))
    escalation_type: Mapped[str | None] = mapped_column(String(32))
    escalation_reason: Mapped[str | None] = mapped_column(Text)
    escalation_trigger_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id", use_alter=True, name="fk_chat_sessions_escalation_trigger_message_id")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization: Mapped[Organization] = relationship()
    patient: Mapped[Patient | None] = relationship()
    appointment: Mapped[Appointment | None] = relationship(back_populates="chat_session")
    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        foreign_keys="[ChatMessage.session_id]",
    )
    events: Mapped[list[ChatSessionEvent]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[ChatSession] = relationship(back_populates="messages", foreign_keys=[session_id])


class ChatSessionEvent(Base):
    __tablename__ = "chat_session_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_data_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[ChatSession] = relationship(back_populates="events")
