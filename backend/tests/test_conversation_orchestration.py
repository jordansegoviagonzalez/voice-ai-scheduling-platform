from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import Flask
from sqlalchemy import func, select

from app.extensions import get_session_factory
from app.integrations.openai.client import OpenAIIntentAdapter
from app.models import Appointment, Call
from app.services.conversation import ConversationOrchestrator


class FakeProvider:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def create_intent_response(self, *, model: str, raw_user_text: str, timeout_seconds: float) -> dict[str, Any]:
        return dict(self.payload)


def _adapter(payload: dict[str, Any]) -> OpenAIIntentAdapter:
    return OpenAIIntentAdapter(
        api_key=None,
        model="gpt-5.2",
        integration_mode="test",
        timeout_seconds=1,
        max_retries=0,
        provider=FakeProvider(payload),
    )


def _payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "raw_user_text": "I am a new patient with a shoulder fracture.",
        "patient_status": "NEW",
        "body_part": "Shoulder",
        "issue_type": "Fracture",
        "preferred_doctor_name": "Dr. Elena Vasquez",
        "preferred_location_code": "MAIN",
        "clarification_required": False,
        "clarification_question": None,
        "caller_correction": None,
    }
    payload.update(overrides)
    return payload


def test_orchestrator_requests_clarification_for_incomplete_intent(app: Flask) -> None:
    session = get_session_factory()()
    result = ConversationOrchestrator(
        session,
        app,
        _adapter(
            _payload(
                patient_status="UNKNOWN",
                body_part=None,
                issue_type=None,
                preferred_doctor_name=None,
                preferred_location_code=None,
                clarification_required=True,
                clarification_question="Which body part is the appointment for?",
            )
        ),
    ).interpret(raw_user_text="I need an appointment")
    session.close()
    assert result["status"] == "clarification_required"
    assert result["routing"] is None
    assert result["missing_fields"] == ["patient_status", "body_part", "issue_type"]


def test_orchestrator_routes_complete_intent_without_booking(app: Flask) -> None:
    session = get_session_factory()()
    before = session.scalar(select(func.count(Appointment.id)))
    result = ConversationOrchestrator(session, app, _adapter(_payload())).interpret(raw_user_text="shoulder fracture")
    after = session.scalar(select(func.count(Appointment.id)))
    session.close()
    assert result["status"] == "routing_ready"
    assert result["routing"]["recommended"] is not None
    assert after == before


def test_orchestrator_applies_caller_correction_to_state(app: Flask) -> None:
    session = get_session_factory()()
    result = ConversationOrchestrator(
        session,
        app,
        _adapter(
            _payload(
                issue_type="General",
                caller_correction={
                    "issue_type": "Fracture",
                },
            )
        ),
    ).interpret(
        raw_user_text="Actually this is a fracture.",
        previous_state={"patient_status": "NEW", "body_part": "Shoulder", "issue_type": "General"},
    )
    session.close()
    assert result["status"] == "routing_ready"
    assert result["state"]["issue_type"] == "Fracture"


def test_conversation_state_is_reconstructable_after_new_session(app: Flask) -> None:
    session = get_session_factory()()
    call = Call(
        status="IN_PROGRESS",
        caller_phone="+18055556666",
        started_at=datetime.now(UTC),
        transcript=[],
    )
    session.add(call)
    session.commit()
    call_id = call.id

    partial = ConversationOrchestrator(
        session,
        app,
        _adapter(
            _payload(
                issue_type=None,
                preferred_doctor_name=None,
                preferred_location_code=None,
                clarification_required=True,
                clarification_question="Is this for a fracture, joint replacement, sports injury, or general pain?",
            )
        ),
    ).interpret(raw_user_text="I am new and need shoulder care.", call_id=call_id)
    session.commit()
    session.close()

    resumed = get_session_factory()()
    stored = resumed.get(Call, call_id)
    assert stored is not None
    assert partial["status"] == "clarification_required"
    assert stored.patient_status == "NEW"
    assert stored.requested_body_part == "Shoulder"
    assert stored.requested_issue_type is None

    previous_state = {
        "patient_status": stored.patient_status,
        "body_part": stored.requested_body_part,
        "issue_type": stored.requested_issue_type,
    }
    corrected = ConversationOrchestrator(
        resumed,
        app,
        _adapter(
            _payload(
                patient_status="UNKNOWN",
                body_part=None,
                issue_type="Fracture",
                preferred_doctor_name=None,
                preferred_location_code=None,
                caller_correction={"issue_type": "Fracture"},
            )
        ),
    ).interpret(raw_user_text="It is a fracture.", previous_state=previous_state, call_id=call_id)
    resumed.commit()
    refreshed = resumed.get(Call, call_id)
    resumed.close()

    assert corrected["status"] == "routing_ready"
    assert refreshed is not None
    assert refreshed.requested_body_part == "Shoulder"
    assert refreshed.requested_issue_type == "Fracture"
