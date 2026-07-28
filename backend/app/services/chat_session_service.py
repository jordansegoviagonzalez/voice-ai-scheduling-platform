from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.domain.chat.chat_state import ChatState
from app.domain.chat.chat_steps import ChatStep
from app.models import Patient
from app.models.chat import ChatMessage, ChatSession, ChatSessionEvent

TERMINAL_STATES = {ChatState.CONFIRMED, ChatState.ESCALATED, ChatState.CARE_TEAM_HANDOFF, ChatState.ABANDONED}
RESUMABLE_STATES = {ChatState.COLLECTING_INTAKE, ChatState.ROUTING, ChatState.SELECTING_APPOINTMENT}
WELCOME_MESSAGES = {
    "new": "Welcome, {first_name}. What is the reason for your visit today?",
    "returning": "Welcome back, {first_name}. What is the reason for your visit today?",
}


class ChatSessionService:
    def __init__(self, db_session: Session):
        self.session = db_session

    def create_session(self, patient_mode: str | None) -> ChatSession:
        chat_session = ChatSession(
            status=ChatState.PATIENT_ACCESS,
            current_step=ChatStep.IDENTIFY_PATIENT,
            collected_data_json={"patient_type": patient_mode} if patient_mode else {},
        )
        self.session.add(chat_session)
        self.session.commit()
        return chat_session

    def create_patient_session(self, *, patient: Patient, patient_type: str) -> ChatSession:
        if patient_type not in WELCOME_MESSAGES:
            raise ValueError("patient_type must be new or returning")
        chat_session = ChatSession(
            patient_id=patient.id,
            status=ChatState.COLLECTING_INTAKE,
            current_step=ChatStep.COLLECT_INTAKE,
            collected_data_json=_patient_collected_data(patient, patient_type),
        )
        self.session.add(chat_session)
        self.session.flush()
        self._add_uncommitted_message(
            chat_session.id,
            "assistant",
            _welcome_message(patient, patient_type),
        )
        self.session.commit()
        return chat_session

    def find_patient_session(
        self,
        *,
        session_ids: list[int],
        patient_id: int,
        patient_type: str,
    ) -> ChatSession | None:
        if not session_ids:
            return None
        sessions = self.session.scalars(
            select(ChatSession)
            .where(
                ChatSession.id.in_(session_ids),
                ChatSession.patient_id == patient_id,
                ChatSession.status.in_(RESUMABLE_STATES),
                ChatSession.completed_at.is_(None),
            )
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        ).all()
        for chat_session in sessions:
            if (chat_session.collected_data_json or {}).get("patient_type") == patient_type:
                return chat_session
        return None

    def find_latest_resumable_patient_session(self, *, patient_id: int) -> ChatSession | None:
        return self.session.scalar(
            select(ChatSession)
            .where(
                ChatSession.patient_id == patient_id,
                ChatSession.status.in_(RESUMABLE_STATES),
                ChatSession.completed_at.is_(None),
            )
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        )

    def get_session(self, session_id: int) -> ChatSession | None:
        return self.session.get(ChatSession, session_id)

    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        chat_session = self.get_session(session_id)
        if not chat_session:
            raise ValueError("Session not found")

        seq = (
            self.session.scalar(
                select(func.coalesce(func.max(ChatMessage.sequence_number), 0)).where(
                    ChatMessage.session_id == session_id
                )
            )
            or 0
        ) + 1
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sequence_number=seq,
            metadata_json=metadata,
            created_at=datetime.now(UTC),
        )
        self.session.add(msg)
        self.session.commit()
        return msg

    def ensure_welcome_message(self, chat_session: ChatSession, patient: Patient, patient_type: str) -> ChatMessage:
        content = _welcome_message(patient, patient_type)
        existing = self.session.scalar(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == chat_session.id,
                ChatMessage.role == "assistant",
                ChatMessage.content == content,
            )
            .order_by(ChatMessage.sequence_number)
        )
        if existing is not None:
            return existing
        return self.add_message(chat_session.id, "assistant", content)

    def _add_uncommitted_message(
        self,
        session_id: int,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        seq = (
            self.session.scalar(
                select(func.coalesce(func.max(ChatMessage.sequence_number), 0)).where(
                    ChatMessage.session_id == session_id
                )
            )
            or 0
        ) + 1
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            sequence_number=seq,
            metadata_json=metadata,
            created_at=datetime.now(UTC),
        )
        self.session.add(msg)
        return msg

    def get_recent_messages(self, session_id: int, limit: int = 10) -> list[dict[str, str]]:
        messages = self.session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.sequence_number.desc())
            .limit(limit)
        ).all()
        return [{"role": m.role, "content": m.content} for m in reversed(messages)]

    def update_session_state(
        self,
        session_id: int,
        status: str | None = None,
        current_step: str | None = None,
        collected_data: dict[str, Any] | None = None,
        routing_result: dict[str, Any] | None = None,
        escalation_type: str | None = None,
        escalation_reason: str | None = None,
        trigger_message_id: int | None = None,
        patient_id: int | None = None,
        appointment_id: int | None = None,
    ) -> ChatSession:
        chat_session = self.get_session(session_id)
        if not chat_session:
            raise ValueError("Session not found")

        if status:
            chat_session.status = status
        if current_step:
            chat_session.current_step = current_step
        if collected_data is not None:
            chat_session.collected_data_json = collected_data
            flag_modified(chat_session, "collected_data_json")
        if routing_result is not None:
            chat_session.routing_result_json = routing_result
            flag_modified(chat_session, "routing_result_json")
        if escalation_type:
            chat_session.escalation_type = escalation_type
        if escalation_reason:
            chat_session.escalation_reason = escalation_reason
        if trigger_message_id:
            chat_session.escalation_trigger_message_id = trigger_message_id
        if patient_id:
            chat_session.patient_id = patient_id
        if appointment_id:
            chat_session.appointment_id = appointment_id
        if status in TERMINAL_STATES and chat_session.completed_at is None:
            chat_session.completed_at = datetime.now(UTC)

        self.session.commit()
        return chat_session

    def log_event(self, session_id: int, event_type: str, event_data: dict[str, Any] | None = None) -> ChatSessionEvent:
        event = ChatSessionEvent(
            session_id=session_id, event_type=event_type, event_data_json=event_data, created_at=datetime.now(UTC)
        )
        self.session.add(event)
        self.session.commit()
        return event


def _patient_collected_data(patient: Patient, patient_type: str) -> dict[str, Any]:
    return {
        "patient_type": patient_type,
        "full_name": patient.full_name,
        "date_of_birth": patient.date_of_birth.isoformat(),
        "phone": patient.phone,
        "email": patient.email,
        "insurance_provider": patient.insurance_provider,
    }


def _welcome_message(patient: Patient, patient_type: str) -> str:
    template = WELCOME_MESSAGES[patient_type]
    return template.format(first_name=patient.first_name)
