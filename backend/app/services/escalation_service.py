from app.domain.chat.chat_state import ChatState
from app.services.chat_session_service import ChatSessionService


class EscalationService:
    def __init__(self, chat_session_service: ChatSessionService):
        self.chat_session_service = chat_session_service

    def escalate_session(self, session_id: int, escalation_type: str, reason: str, trigger_message_id: int) -> None:
        status = ChatState.ESCALATED if escalation_type == "emergency" else ChatState.CARE_TEAM_HANDOFF
        self.chat_session_service.update_session_state(
            session_id=session_id,
            status=status,
            escalation_type=escalation_type,
            escalation_reason=reason,
            trigger_message_id=trigger_message_id,
        )
        self.chat_session_service.log_event(session_id, "escalated", {"type": escalation_type, "reason": reason})
