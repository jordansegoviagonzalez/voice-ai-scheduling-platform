from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from flask import Flask
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.chat.chat_state import ChatState
from app.domain.chat.chat_steps import ChatStep
from app.domain.routing import PhysicianRoutingService
from app.domain.rules.care_team_handoff_rules import HANDOFF_MESSAGE
from app.domain.rules.emergency_rules import EMERGENCY_MESSAGE
from app.domain.rules.intake_validation import validate_intake_fields
from app.errors import ApiError
from app.extensions import get_session_factory
from app.models import ChatSession, Patient
from app.services.ai_intake_service import AIIntakeService
from app.services.booking import BookingService
from app.services.chat_session_service import ChatSessionService
from app.services.chat_workflow_service import ChatWorkflowService
from app.services.escalation_service import EscalationService
from app.services.organization_context import default_organization_id
from app.services.patient_access_service import PatientAccessService

TIME_QUESTION = "Do you prefer morning, afternoon, or does any time work?"
LOCATION_QUESTION = "Which location do you prefer: Main, East, North, West, or South?"


class FakeIntakeClient:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def analyze_message(
        self,
        current_state: str,
        recent_messages: list[dict[str, str]],
        latest_message: str,
        required_fields: list[str],
    ) -> dict[str, Any]:
        return self.payload


def _response(**overrides: Any) -> dict[str, Any]:
    payload = {
        "intent": "collect_intake",
        "assistant_message": "Next question.",
        "extracted_fields": {},
        "corrections": [],
        "off_topic": False,
        "possible_emergency": False,
        "handoff_requested": False,
        "confidence": 0.95,
    }
    payload.update(overrides)
    return payload


def _session(collected: dict[str, Any] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        current_step="collect_intake",
        collected_data_json=collected or {"patient_type": "returning"},
    )


def test_follow_up_answer_does_not_overwrite_existing_sports_medicine_issue_type() -> None:
    service = AIIntakeService(
        FakeIntakeClient(
            _response(
                extracted_fields={
                    "appointment_type": "follow_up",
                    "chief_complaint": "Right knee pain",
                    "issue_type": "General",
                }
            )
        )
    )

    result = service.process_message(
        session=_session(
            {
                "patient_type": "returning",
                "chief_complaint": "Right knee pain from a sports injury",
                "body_part": "Knee",
                "side": "right",
                "issue_type": "Sports Medicine",
            }
        ),
        recent_messages=[],
        latest_message="this is a follow up yeah",
    )

    assert result.updated_data["appointment_type"] == "follow_up"
    assert result.updated_data["issue_type"] == "Sports Medicine"
    assert result.updated_data["chief_complaint"] == "Right knee pain from a sports injury"


def test_earliest_available_appointment_completes_scheduling_preference() -> None:
    service = AIIntakeService(
        FakeIntakeClient(
            _response(
                extracted_fields={
                    "preferred_date_or_time": "earliest possible",
                    "preferred_time_of_day": "morning",
                }
            )
        )
    )

    result = service.process_message(
        session=_session(
            {
                "patient_type": "returning",
                "chief_complaint": "Right knee pain from a sports injury",
                "body_part": "Knee",
                "side": "right",
                "symptom_duration": "about two weeks",
                "severity": 9,
                "appointment_type": "follow_up",
                "issue_type": "Sports Medicine",
                "preferred_location": "NORTH",
            }
        ),
        recent_messages=[],
        latest_message="I would like the earliest available appointment.",
    )

    assert result.updated_data["preferred_date_or_time"] == "earliest possible"
    assert result.updated_data["preferred_time_of_day"] == "any"
    assert result.assistant_reply != TIME_QUESTION


@pytest.mark.parametrize(
    "message",
    [
        "earliest available",
        "earliest available appointment",
        "first available",
        "first appointment available",
        "soonest available",
        "soonest appointment",
        "as soon as possible",
        "whenever the first opening is",
        "any time, as long as it is the earliest",
        "I do not care what time, give me the earliest",
    ],
)
def test_availability_order_language_normalizes_to_earliest_possible_any_time(message: str) -> None:
    service = AIIntakeService(FakeIntakeClient(_response()))

    result = service.process_message(session=_session(), recent_messages=[], latest_message=message)

    assert result.updated_data["preferred_date_or_time"] == "earliest possible"
    assert result.updated_data["preferred_time_of_day"] == "any"
    assert result.assistant_reply != TIME_QUESTION


@pytest.mark.parametrize(
    "message",
    ["morning", "mornings", "in the morning", "any morning", "morning works", "I prefer mornings"],
)
def test_morning_time_preference_aliases_validate_to_canonical_morning(message: str) -> None:
    clean_fields, errors = validate_intake_fields({"preferred_time_of_day": message})

    assert errors == {}
    assert clean_fields["preferred_time_of_day"] == "morning"


def test_existing_time_preference_is_not_overwritten_without_explicit_correction() -> None:
    service = AIIntakeService(FakeIntakeClient(_response(extracted_fields={"preferred_time_of_day": "afternoon"})))

    result = service.process_message(
        session=_session({"patient_type": "returning", "preferred_time_of_day": "morning"}),
        recent_messages=[],
        latest_message="Can you keep going?",
    )

    assert result.updated_data["preferred_time_of_day"] == "morning"


def test_existing_time_preference_is_preserved_when_earliest_date_is_added() -> None:
    service = AIIntakeService(FakeIntakeClient(_response()))

    result = service.process_message(
        session=_session({"patient_type": "returning", "preferred_time_of_day": "morning"}),
        recent_messages=[],
        latest_message="earliest available appointment",
    )

    assert result.updated_data["preferred_time_of_day"] == "morning"
    assert result.updated_data["preferred_date_or_time"] == "earliest possible"


def test_model_declared_unsupported_complaint_returns_care_team_handoff() -> None:
    service = AIIntakeService(FakeIntakeClient(_response(handoff_requested=True)))

    result = service.process_message(
        session=_session(),
        recent_messages=[],
        latest_message="I need help with elbow pain",
    )

    assert result.escalation_type == "care_team_handoff"
    assert result.assistant_reply == HANDOFF_MESSAGE
    assert "No physician matches" not in result.assistant_reply


def test_possible_emergency_still_stops_scheduling() -> None:
    service = AIIntakeService(FakeIntakeClient(_response()))

    result = service.process_message(
        session=_session(),
        recent_messages=[],
        latest_message="I have chest pain and trouble breathing",
    )

    assert result.escalation_type == "emergency"
    assert result.assistant_reply == EMERGENCY_MESSAGE


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("I being felling this way for about two weeks", {"symptom_duration": "about two weeks"}),
        ("I mean earliest possible", {"preferred_date_or_time": "earliest possible"}),
        ("soonest available", {"preferred_date_or_time": "earliest possible", "preferred_time_of_day": "any"}),
        ("as soon as possible", {"preferred_date_or_time": "earliest possible", "preferred_time_of_day": "any"}),
        ("first available", {"preferred_date_or_time": "earliest possible", "preferred_time_of_day": "any"}),
        ("morning", {"preferred_time_of_day": "morning", "preferred_date_or_time": "earliest possible"}),
        ("mornings", {"preferred_time_of_day": "morning", "preferred_date_or_time": "earliest possible"}),
        ("I prefer mornings", {"preferred_time_of_day": "morning"}),
        ("early morning", {"preferred_time_of_day": "morning", "preferred_date_or_time": "earliest possible"}),
        ("afternoon", {"preferred_time_of_day": "afternoon", "preferred_date_or_time": "earliest possible"}),
        ("any time works", {"preferred_time_of_day": "any", "preferred_date_or_time": "earliest possible"}),
        ("this is a follow up yeah", {"appointment_type": "follow_up"}),
        ("right nee pain", {"body_part": "Knee", "side": "right", "issue_type": "General"}),
        ("north clinc", {"preferred_location": "NORTH"}),
        ("east clinic", {"preferred_location": "EAST"}),
        ("south clinic", {"preferred_location": "SOUTH"}),
        ("earliest available at any location", {"preferred_location": "ANY"}),
        ("elbow pain", {"body_part": "Elbow", "issue_type": "General"}),
        ("upper arm pain", {"body_part": "Upper Arm", "issue_type": "General"}),
        ("lower leg pain", {"body_part": "Lower Leg", "issue_type": "General"}),
        ("heart hurts", {"body_part": "Heart/Circulation", "issue_type": "Pain"}),
        ("palpitations", {"body_part": "Heart/Circulation"}),
        ("tongue hurts", {"body_part": "Mouth/Teeth/Tongue", "issue_type": "Pain"}),
        ("tooth pain", {"body_part": "Mouth/Teeth/Tongue", "issue_type": "Pain"}),
        ("earache", {"body_part": "Ear/Nose/Throat", "issue_type": "Pain"}),
        ("sore throat", {"body_part": "Ear/Nose/Throat", "issue_type": "Pain"}),
        ("rash", {"body_part": "Skin/Hair/Nails", "issue_type": "Rash/Itching"}),
        ("stomach pain", {"body_part": "Digestive/Abdomen", "issue_type": "Pain"}),
        (
            "I have right knee pain from a sports injury",
            {"body_part": "Knee", "side": "right", "issue_type": "Sports Medicine"},
        ),
        ("I would say a 9.", {"severity": 9}),
    ],
)
def test_typo_filled_messages_are_normalized_without_rewriting_patient_text(
    message: str, expected: dict[str, Any]
) -> None:
    service = AIIntakeService(FakeIntakeClient(_response()))

    result = service.process_message(session=_session(), recent_messages=[], latest_message=message)

    for field, value in expected.items():
        assert result.updated_data[field] == value
    if "chief_complaint" in result.updated_data:
        assert result.updated_data["chief_complaint"] == message


@pytest.mark.parametrize("message", ["0 out of 10", "-1", "11 out of 10"])
def test_severity_must_be_1_to_10(message: str) -> None:
    service = AIIntakeService(FakeIntakeClient(_response()))

    result = service.process_message(session=_session(), recent_messages=[], latest_message=message)

    assert result.invalid_fields == {"severity": "Severity must be between 1 and 10."}
    assert "severity" not in result.updated_data


@pytest.mark.parametrize(
    ("message", "expected_time"),
    [
        ("morning", "morning"),
        ("mornings", "morning"),
        ("I prefer mornings", "morning"),
        ("afternoon", "afternoon"),
        ("any time works", "any"),
    ],
)
def test_valid_time_preference_advances_olivia_workflow_to_real_slots(
    app: Flask, message: str, expected_time: str
) -> None:
    assert app.testing
    db_session = get_session_factory()()
    try:
        chat_service = ChatSessionService(db_session)
        workflow = _workflow(db_session, chat_service)
        session_id = _create_olivia_session_at_time_preference(db_session, chat_service)

        payload = workflow.handle_message(session_id, message)

        assert payload["status"] == ChatState.SELECTING_APPOINTMENT
        assert payload["currentStep"] == ChatStep.SLOT_SELECTION
        assert payload["collectedData"]["preferred_time_of_day"] == expected_time
        assert payload["collectedData"]["preferred_date_or_time"] == "earliest possible"
        assert payload["assistantMessage"]["content"] != TIME_QUESTION
        assert _assistant_question_count(payload["messages"], TIME_QUESTION) == 1
        assert any(m["role"] == "patient" and m["content"] == message for m in payload["messages"])

        first = payload["recommendations"][0]
        first_loc = first["locations"][0]
        first_slot = first_loc["available_slots"][0]
        assert first["physician_name"] == "Dr. James Walsh"
        assert first_loc["clinic_location_code"] == "NORTH"
        assert first_slot["location"]["code"] == "NORTH"
        if expected_time == "morning":
            assert first_slot["display_time"].endswith("AM")
        assert first_slot["id"] is not None
    finally:
        db_session.close()


def test_ambiguous_time_preference_gets_one_concise_clarification(app: Flask) -> None:
    assert app.testing
    db_session = get_session_factory()()
    try:
        chat_service = ChatSessionService(db_session)
        workflow = _workflow(db_session, chat_service)
        session_id = _create_olivia_session_at_time_preference(db_session, chat_service)

        payload = workflow.handle_message(session_id, "later maybe")

        assert payload["status"] == ChatState.COLLECTING_INTAKE
        assert payload["assistantMessage"]["content"] == TIME_QUESTION
        assert "preferred_time_of_day" not in payload["collectedData"]
        assert _assistant_question_count(payload["messages"], TIME_QUESTION) == 2
    finally:
        db_session.close()


def test_saved_time_preference_advances_on_next_message_without_duplicate_question(app: Flask) -> None:
    assert app.testing
    db_session = get_session_factory()()
    try:
        chat_service = ChatSessionService(db_session)
        workflow = _workflow(db_session, chat_service)
        session_id = _create_olivia_session_at_time_preference(
            db_session,
            chat_service,
            preferred_time_of_day="morning",
        )

        payload = workflow.handle_message(session_id, "morning")

        assert payload["status"] == ChatState.SELECTING_APPOINTMENT
        assert payload["collectedData"]["preferred_time_of_day"] == "morning"
        assert payload["collectedData"]["preferred_date_or_time"] == "earliest possible"
        assert payload["assistantMessage"]["content"] != TIME_QUESTION
        assert _assistant_question_count(payload["messages"], TIME_QUESTION) == 1
    finally:
        db_session.close()


def test_sophia_new_patient_earliest_available_gets_alternative_location_and_can_book(app: Flask) -> None:
    assert app.testing
    db_session = get_session_factory()()
    try:
        chat_service = ChatSessionService(db_session)
        workflow = _workflow(db_session, chat_service)
        session_id = _create_sophia_session_at_availability_preference(db_session, chat_service)

        payload = workflow.handle_message(session_id, "I would like the earliest available appointment.")

        assert payload["status"] == ChatState.SELECTING_APPOINTMENT
        assert payload["currentStep"] == ChatStep.SLOT_SELECTION
        assert payload["collectedData"]["body_part"] == "Foot/Ankle"
        assert payload["collectedData"]["issue_type"] == "General"
        assert payload["collectedData"]["appointment_type"] == "new_patient"
        assert payload["collectedData"]["preferred_location"] == "MAIN"
        assert payload["collectedData"]["preferred_date_or_time"] == "earliest possible"
        assert payload["collectedData"]["preferred_time_of_day"] == "any"
        assert payload["assistantMessage"]["content"] != TIME_QUESTION
        assert _assistant_question_count(payload["messages"], TIME_QUESTION) == 1

        normalized = payload["routingResult"]["normalized_request"]
        assert normalized["patient_status"] == "NEW"
        assert normalized["body_part"] == "Foot/Ankle"
        assert normalized["issue_type"] == "General"
        assert normalized["preferred_location_id"] is not None
        assert normalized["preferred_location"]["code"] == "MAIN"

        assert [item["physician_name"] for item in payload["recommendations"]] == [
            "Dr. James Walsh",
            "Dr. Carlos Mendez",
            "Dr. David Nguyen",
        ]
        assert [item["specialty"] for item in payload["recommendations"]] == [
            "Foot and Ankle Orthopedics",
            "Foot and Ankle Orthopedics",
            "General Orthopedics",
        ]
        assert [item["is_general_orthopedics"] for item in payload["recommendations"]].count(True) == 1
        assert all(
            any("Alternative location" in loc["labels"] for loc in item["locations"])
            for item in payload["recommendations"]
        )
        assert "General Orthopedics" in payload["recommendations"][2]["labels"]
        assert payload["routingResult"]["location_fallback"]["preferred_location"]["code"] == "MAIN"
        assert payload["routingResult"]["location_fallback"]["selected_location"]["code"] == "NORTH"
        assert "No matching opening was available at Main Campus" in payload["recommendations"][0]["match_explanation"]
        assert "No physician matches" not in payload["assistantMessage"]["content"]
        assert "Main Campus" in payload["assistantMessage"]["content"]
        assert "Patient eligibility rules" not in payload["assistantMessage"]["content"]

        recommendation = payload["recommendations"][2]
        slot_id = recommendation["locations"][0]["available_slots"][0]["id"]
        workflow.select_appointment(session_id, slot_id)
        booked_payload, status_code = workflow.confirm_appointment(session_id)
        assert status_code == 200
        assert booked_payload["status"] == ChatState.CONFIRMED
        assert booked_payload["booking"]["doctor"]["last_name"] == "Nguyen"
        assert booked_payload["routingResult"]["selected_slot_id"] == booked_payload["booking"]["slot"]["id"]
        assert booked_payload["routingResult"]["selected_recommendation"]["physician_name"] == "Dr. David Nguyen"
        assert booked_payload["booking"]["body_part"] == "Foot/Ankle"
        assert booked_payload["booking"]["issue_type"] == "General"
        assert booked_payload["booking"]["patient"]["full_name"] == "Sophia Martinez"
    finally:
        db_session.close()


def test_select_appointment_rejects_unoffered_slot(app: Flask) -> None:
    assert app.testing
    db_session = get_session_factory()()
    try:
        chat_service = ChatSessionService(db_session)
        workflow = _workflow(db_session, chat_service)
        session_id = _create_sophia_session_at_availability_preference(db_session, chat_service)

        payload = workflow.handle_message(session_id, "I would like the earliest available appointment.")
        assert payload["status"] == ChatState.SELECTING_APPOINTMENT

        # Pick a slot that doesn't exist (999999)
        with pytest.raises(ApiError) as exc:
            workflow.select_appointment(session_id, 999999)

        assert exc.value.status_code == 422
        assert exc.value.code == "SLOT_NOT_OFFERED"
    finally:
        db_session.close()


def test_select_appointment_requires_valid_status(app: Flask) -> None:
    assert app.testing
    db_session = get_session_factory()()
    try:
        chat_service = ChatSessionService(db_session)
        workflow = _workflow(db_session, chat_service)
        session_id = _create_sophia_session_at_availability_preference(db_session, chat_service)

        # We haven't offered slots yet, session is in INTAKE
        with pytest.raises(ApiError) as exc:
            workflow.select_appointment(session_id, 101)

        assert exc.value.status_code == 409
        assert exc.value.code == "SESSION_NOT_READY"
    finally:
        db_session.close()


def test_web_recommendations_deduplicate_identical_slots(app: Flask) -> None:
    assert app.testing
    db_session = get_session_factory()()
    try:
        workflow = _workflow(db_session, ChatSessionService(db_session))
        duplicated_slot = {
            "id": 101,
            "doctor_id": 7,
            "starts_at": "2026-07-28T09:00:00+00:00",
            "ends_at": "2026-07-28T09:45:00+00:00",
            "status": "OPEN",
            "location": {"id": 2, "code": "NORTH", "name": "North Clinic"},
        }
        routing_result = {
            "normalized_request": {
                "preferred_location": {"id": 1, "code": "MAIN", "name": "Main Campus"},
            },
            "ranked_recommendations": [
                {
                    "doctor": {
                        "id": 7,
                        "first_name": "David",
                        "last_name": "Nguyen",
                        "full_name": "Dr. David Nguyen",
                    },
                    "has_patient_history": False,
                    "preferred_location_match": False,
                    "available_slots": [
                        duplicated_slot,
                        {**duplicated_slot, "id": 102},
                        {**duplicated_slot, "id": 103, "starts_at": "2026-07-28T11:00:00+00:00"},
                    ],
                }
            ],
        }

        recommendations = workflow._web_recommendations(
            routing_result,
            {"body_part": "Foot/Ankle", "issue_type": "General", "preferred_time_of_day": "any"},
        )

        slot_ids = [slot["id"] for loc in recommendations[0]["locations"] for slot in loc["available_slots"]]
        assert slot_ids == [101, 103]
        assert any("Alternative location" in loc["labels"] for loc in recommendations[0]["locations"])
    finally:
        db_session.close()


def _workflow(db_session: Session, chat_service: ChatSessionService) -> ChatWorkflowService:
    return ChatWorkflowService(
        organization_id=default_organization_id(db_session),
        db_session=db_session,
        chat_service=chat_service,
        patient_access=PatientAccessService(db_session),
        ai_intake=AIIntakeService(FakeIntakeClient(_response())),
        escalation=EscalationService(chat_service),
        routing=PhysicianRoutingService(db_session),
        booking=BookingService(db_session),
    )


def _create_olivia_session_at_time_preference(
    db_session: Session,
    chat_service: ChatSessionService,
    *,
    preferred_time_of_day: str | None = None,
) -> int:
    olivia = db_session.scalar(select(Patient).where(Patient.email == "olivia.carter.phase2.demo@example.com"))
    assert olivia is not None
    collected_data: dict[str, Any] = {
        "patient_type": "returning",
        "full_name": olivia.full_name,
        "date_of_birth": olivia.date_of_birth.isoformat(),
        "phone": olivia.phone,
        "email": olivia.email,
        "chief_complaint": "Right knee pain from a sports injury",
        "body_part": "Knee",
        "side": "right",
        "issue_type": "Sports Medicine",
        "symptom_duration": "about two weeks",
        "severity": 9,
        "appointment_type": "follow_up",
        "preferred_location": "NORTH",
    }
    if preferred_time_of_day is not None:
        collected_data["preferred_time_of_day"] = preferred_time_of_day
    chat_session = ChatSession(
        organization_id=default_organization_id(db_session),
        patient_id=olivia.id,
        status=ChatState.COLLECTING_INTAKE,
        current_step=ChatStep.COLLECT_INTAKE,
        collected_data_json=collected_data,
    )
    db_session.add(chat_session)
    db_session.commit()
    chat_service.add_message(chat_session.id, "assistant", TIME_QUESTION)
    return chat_session.id


def _create_sophia_session_at_availability_preference(
    db_session: Session,
    chat_service: ChatSessionService,
) -> int:
    sophia = Patient(
        first_name="Sophia",
        last_name="Martinez",
        date_of_birth=datetime.fromisoformat("1991-04-18").date(),
        phone="+18055559011",
        email="sophia.martinez@example.test",
        insurance_provider="Demo Health",
    )
    db_session.add(sophia)
    db_session.flush()
    chat_session = ChatSession(
        organization_id=default_organization_id(db_session),
        patient_id=sophia.id,
        status=ChatState.COLLECTING_INTAKE,
        current_step=ChatStep.COLLECT_INTAKE,
        collected_data_json={
            "patient_type": "new",
            "full_name": sophia.full_name,
            "date_of_birth": sophia.date_of_birth.isoformat(),
            "phone": sophia.phone,
            "email": sophia.email,
            "insurance_provider": sophia.insurance_provider,
            "chief_complaint": "Left ankle pain after twisting it stepping off a curb",
            "body_part": "Foot/Ankle",
            "side": "left",
            "symptom_duration": "three days",
            "severity": 6,
            "appointment_type": "new_patient",
            "issue_type": "General",
            "preferred_location": "MAIN",
        },
    )
    db_session.add(chat_session)
    db_session.commit()
    chat_service.add_message(chat_session.id, "assistant", TIME_QUESTION)
    return chat_session.id


def _assistant_question_count(messages: list[dict[str, Any]], question: str) -> int:
    return sum(1 for message in messages if message["role"] == "assistant" and message["content"] == question)
