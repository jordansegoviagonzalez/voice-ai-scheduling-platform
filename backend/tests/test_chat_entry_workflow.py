from __future__ import annotations

from datetime import UTC, date, datetime

from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import func, select

from app.domain.chat.chat_state import ChatState
from app.domain.chat.chat_steps import ChatStep
from app.extensions import get_session_factory
from app.models import ChatMessage, ChatSession, Patient

GENERIC_ENTRY_QUESTION = "Hi, I can help you schedule an orthopedic appointment. Are you a new or returning patient?"


def test_new_patient_registration_creates_linked_session_with_personalized_welcome(
    client: FlaskClient,
) -> None:
    response = client.post("/api/chat/sessions", json=_new_patient_payload())

    assert response.status_code == 201, response.get_json()
    payload = response.get_json()
    assert payload["status"] == ChatState.COLLECTING_INTAKE
    assert payload["currentStep"] == ChatStep.COLLECT_INTAKE
    assert payload["patient"]["fullName"] == "Jose Rivera"
    assert payload["collectedData"]["patient_type"] == "new"
    assert payload["collectedData"]["full_name"] == "Jose Rivera"
    assert payload["collectedData"]["insurance_provider"] == "Acme Health"
    assert payload["messages"] == [
        {
            "role": "assistant",
            "content": "Welcome, Jose. What is the reason for your visit today?",
            "sequenceNumber": 1,
        }
    ]
    assert payload["assistantMessage"]["content"] == "Welcome, Jose. What is the reason for your visit today?"
    assert GENERIC_ENTRY_QUESTION not in _message_text(payload)
    assert "What is your full name?" not in _message_text(payload)


def test_new_patient_registration_reuses_patient_without_duplicate_patient_record(
    app: Flask,
    client: FlaskClient,
) -> None:
    first = client.post("/api/chat/sessions", json=_new_patient_payload())
    second = client.post("/api/chat/sessions", json=_new_patient_payload())

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.get_json()["sessionId"] == first.get_json()["sessionId"]
    assert _welcome_count(second.get_json(), "Welcome, Jose. What is the reason for your visit today?") == 1

    session = get_session_factory()()
    try:
        patient_count = session.scalar(
            select(func.count(Patient.id)).where(
                Patient.phone == "+18055554001",
                Patient.date_of_birth == date(1994, 5, 4),
            )
        )
        assert patient_count == 1
    finally:
        session.close()
    assert app.testing


def test_failed_new_patient_registration_does_not_create_personalized_welcome(
    client: FlaskClient,
) -> None:
    response = client.post(
        "/api/chat/sessions",
        json={**_new_patient_payload(), "dateOfBirth": "2999-01-01"},
    )

    assert response.status_code == 422
    assert "Jose" not in response.get_json()["error"]["message"]
    with client.session_transaction() as browser_session:
        assert browser_session.get("patient_chat_session_ids") in (None, [])


def test_returning_patient_authentication_creates_one_personalized_welcome(client: FlaskClient) -> None:
    response = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )

    assert response.status_code == 201, response.get_json()
    payload = response.get_json()
    assert isinstance(payload["patient"]["id"], int)
    assert payload["patient"]["fullName"] == "Olivia Carter"
    assert payload["collectedData"]["patient_type"] == "returning"
    assert payload["messages"] == [
        {
            "role": "assistant",
            "content": "Welcome back, Olivia. What is the reason for your visit today?",
            "sequenceNumber": 1,
        }
    ]
    assert GENERIC_ENTRY_QUESTION not in _message_text(payload)


def test_failed_returning_patient_authentication_does_not_expose_patient_identity(
    client: FlaskClient,
) -> None:
    response = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    body = response.get_json()
    assert body["error"]["message"] == "We could not verify those patient details."
    assert "Jordan" not in str(body)
    with client.session_transaction() as browser_session:
        assert browser_session.get("patient_chat_session_ids") in (None, [])


def test_repeated_returning_patient_initialization_and_restore_do_not_duplicate_welcome(
    client: FlaskClient,
) -> None:
    first = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )
    second = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )
    session_id = first.get_json()["sessionId"]
    restored = client.get(f"/api/chat/sessions/{session_id}")
    restored_again = client.get(f"/api/chat/sessions/{session_id}")

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.get_json()["sessionId"] == session_id
    assert _welcome_count(second.get_json(), "Welcome back, Olivia. What is the reason for your visit today?") == 1
    assert _welcome_count(restored.get_json(), "Welcome back, Olivia. What is the reason for your visit today?") == 1
    assert (
        _welcome_count(restored_again.get_json(), "Welcome back, Olivia. What is the reason for your visit today?") == 1
    )


def test_existing_historical_chat_messages_are_not_rewritten(client: FlaskClient) -> None:
    session = get_session_factory()()
    try:
        historical = ChatSession(
            status=ChatState.COLLECTING_INTAKE,
            current_step=ChatStep.COLLECT_INTAKE,
            collected_data_json={"patient_type": "returning"},
        )
        session.add(historical)
        session.flush()
        session.add(
            ChatMessage(
                session_id=historical.id,
                role="assistant",
                content=GENERIC_ENTRY_QUESTION,
                sequence_number=1,
                metadata_json=None,
                created_at=datetime.now(UTC),
            )
        )
        session.commit()
        historical_id = historical.id
    finally:
        session.close()

    with client.session_transaction() as browser_session:
        browser_session["patient_chat_session_ids"] = [historical_id]

    restored = client.get(f"/api/chat/sessions/{historical_id}")

    assert restored.status_code == 200
    assert restored.get_json()["messages"][0]["content"] == GENERIC_ENTRY_QUESTION


def test_unauthorized_patient_session_access_remains_blocked(client: FlaskClient, app: Flask) -> None:
    response = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )
    session_id = response.get_json()["sessionId"]
    other_client = app.test_client()

    unauthorized = other_client.get(f"/api/chat/sessions/{session_id}")

    assert unauthorized.status_code == 401


def _new_patient_payload() -> dict[str, str]:
    return {
        "patientMode": "new",
        "firstName": "Jose",
        "lastName": "Rivera",
        "dateOfBirth": "1994-05-04",
        "phone": "805-555-4001",
        "email": "jose.rivera@example.test",
        "password": "correct horse battery staple",
        "confirmPassword": "correct horse battery staple",
        "insuranceProvider": "Acme Health",
    }


def _message_text(payload: dict[str, object]) -> str:
    return "\n".join(str(message["content"]) for message in payload["messages"])


def _welcome_count(payload: dict[str, object], welcome: str) -> int:
    return sum(1 for message in payload["messages"] if message["role"] == "assistant" and message["content"] == welcome)
