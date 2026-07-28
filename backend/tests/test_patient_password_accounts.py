from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import func, select

from app.domain.chat.chat_state import ChatState
from app.domain.chat.chat_steps import ChatStep
from app.extensions import get_session_factory
from app.models import ChatMessage, ChatSession, Patient
from app.seed import seed_database
from app.services.patient_account_security import verify_patient_password

NEW_PATIENT_PASSWORD = "correct horse battery staple"
GENERIC_LOGIN_FAILURE = "We could not verify those patient details."


def test_new_patient_registration_requires_password_and_confirmation(client: FlaskClient) -> None:
    missing_password = client.post("/api/chat/sessions", json={**_new_patient_payload(), "password": ""})
    missing_confirmation = client.post("/api/chat/sessions", json={**_new_patient_payload(), "confirmPassword": ""})

    assert missing_password.status_code == 422
    assert missing_password.get_json()["error"]["field_errors"]["password"] == ["This field is required"]
    assert missing_confirmation.status_code == 422
    assert missing_confirmation.get_json()["error"]["field_errors"]["confirmPassword"] == ["This field is required"]


def test_new_patient_registration_rejects_mismatched_and_short_passwords(client: FlaskClient) -> None:
    mismatch = client.post(
        "/api/chat/sessions",
        json={**_new_patient_payload(), "confirmPassword": "another safe password"},
    )
    too_short = client.post(
        "/api/chat/sessions",
        json={**_new_patient_payload(), "password": "short", "confirmPassword": "short"},
    )

    assert mismatch.status_code == 422
    assert mismatch.get_json()["error"]["message"] == "Passwords do not match."
    assert too_short.status_code == 422
    assert too_short.get_json()["error"]["field_errors"]["password"] == ["Use at least 12 characters"]


def test_new_patient_password_is_hashed_and_not_exposed_in_api_responses(client: FlaskClient) -> None:
    response = client.post("/api/chat/sessions", json=_new_patient_payload())
    profile = client.get("/api/patient/profile")

    assert response.status_code == 201, response.get_json()
    assert profile.status_code == 200
    payload_text = f"{response.get_json()} {profile.get_json()}"
    assert "password_hash" not in payload_text
    assert NEW_PATIENT_PASSWORD not in payload_text

    patient = _patient_by_email("jose.rivera@example.test")
    assert patient.password_hash is not None
    assert patient.password_hash != NEW_PATIENT_PASSWORD
    assert NEW_PATIENT_PASSWORD not in patient.password_hash
    assert verify_patient_password(patient.password_hash, NEW_PATIENT_PASSWORD)


def test_new_patient_account_credentials_work_after_logout_without_duplicate_patient(
    client: FlaskClient,
) -> None:
    registered = client.post("/api/chat/sessions", json=_new_patient_payload())
    session_id = registered.get_json()["sessionId"]
    patient_id = _patient_by_email("jose.rivera@example.test").id
    before_hash = _patient_by_email("jose.rivera@example.test").password_hash

    logout = client.post("/api/patient/logout")
    restored = client.post(
        "/api/chat/sessions",
        json={
            "patientMode": "returning",
            "email": "jose.rivera@example.test",
            "password": NEW_PATIENT_PASSWORD,
        },
    )

    assert logout.status_code == 200
    assert restored.status_code == 200, restored.get_json()
    assert restored.get_json()["sessionId"] == session_id
    assert _patient_by_email("jose.rivera@example.test").password_hash == before_hash
    assert _patient_count("jose.rivera@example.test") == 1
    assert _patient_by_email("jose.rivera@example.test").id == patient_id


def test_returning_patient_login_uses_generic_failure_for_wrong_or_unknown_credentials(
    client: FlaskClient,
) -> None:
    wrong_password = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "wrong-password"},
    )
    unknown_email = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "unknown.patient@example.test", "password": "wrong-password"},
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.get_json()["error"]["message"] == GENERIC_LOGIN_FAILURE
    assert unknown_email.get_json()["error"]["message"] == GENERIC_LOGIN_FAILURE


def test_jordan_demo_credentials_are_seeded_as_hash_and_seed_remains_idempotent(client: FlaskClient) -> None:
    first = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )
    olivia = _patient_by_email("olivia.carter.phase2.demo@example.com")
    original_id = olivia.id
    original_hash = olivia.password_hash
    original_session_id = first.get_json()["sessionId"]

    session = get_session_factory()()
    try:
        seed_database(session)
        session.commit()
    finally:
        session.close()

    refreshed = _patient_by_email("olivia.carter.phase2.demo@example.com")
    assert first.status_code == 201
    assert refreshed.id == original_id
    assert refreshed.password_hash == original_hash
    assert refreshed.password_hash != "Patient!2026"
    assert verify_patient_password(refreshed.password_hash, "Patient!2026")
    assert _patient_count("olivia.carter.phase2.demo@example.com") == 1
    assert _chat_session_patient_id(original_session_id) == original_id


def test_same_credentials_work_after_logout_and_preserve_unfinished_session(client: FlaskClient) -> None:
    session_id = _sign_in_olivia(client)
    before_hash = _patient_by_email("olivia.carter.phase2.demo@example.com").password_hash

    logout = client.post("/api/patient/logout")
    profile = client.get("/api/patient/profile")
    restored = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )

    assert logout.status_code == 200
    assert profile.status_code == 401
    assert restored.status_code == 200
    assert restored.get_json()["sessionId"] == session_id
    assert _chat_session_exists(session_id)
    assert _patient_by_email("olivia.carter.phase2.demo@example.com").password_hash == before_hash


def test_same_credentials_work_after_session_expiration_without_modifying_password_hash(
    client: FlaskClient,
    monkeypatch,
) -> None:
    import app.services.session_security as session_security

    base_time = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(session_security, "utcnow", lambda: base_time)
    session_id = _sign_in_olivia(client)
    before_hash = _patient_by_email("olivia.carter.phase2.demo@example.com").password_hash

    monkeypatch.setattr(session_security, "utcnow", lambda: base_time + timedelta(minutes=61))
    expired = client.get("/api/patient/profile")
    restored = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )

    assert expired.status_code == 401
    assert expired.get_json()["error"]["code"] == "SESSION_EXPIRED"
    assert restored.status_code == 200
    assert restored.get_json()["sessionId"] == session_id
    assert _chat_session_exists(session_id)
    assert _patient_by_email("olivia.carter.phase2.demo@example.com").password_hash == before_hash


def test_same_credentials_work_from_independent_browser_without_duplicate_patient(
    app: Flask,
    client: FlaskClient,
) -> None:
    first = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )
    other_client = app.test_client()
    second = other_client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.get_json()["sessionId"] == first.get_json()["sessionId"]
    assert _patient_count("olivia.carter.phase2.demo@example.com") == 1


def test_login_restores_latest_owned_unfinished_session_without_duplicating_messages(
    app: Flask,
    client: FlaskClient,
) -> None:
    olivia = _patient_by_email("olivia.carter.phase2.demo@example.com")
    older_id = _create_chat_session(
        olivia.id,
        ChatState.COLLECTING_INTAKE,
        datetime(2026, 7, 27, 12, 0, tzinfo=UTC),
        "Older unfinished session.",
    )
    latest_id = _create_chat_session(
        olivia.id,
        ChatState.SELECTING_APPOINTMENT,
        datetime(2026, 7, 27, 13, 0, tzinfo=UTC),
        "Latest unfinished session.",
        routing_result={"web_recommendations": [{"available_slots": []}]},
    )
    _create_chat_session(
        olivia.id,
        ChatState.CONFIRMED,
        datetime(2026, 7, 27, 14, 0, tzinfo=UTC),
        "Completed historical session.",
        completed=True,
    )
    before_messages = _message_count(latest_id)

    login = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )
    other_client = app.test_client()
    second_login = other_client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )

    assert older_id != latest_id
    assert login.status_code == 200
    assert login.get_json()["sessionId"] == latest_id
    assert second_login.status_code == 200
    assert second_login.get_json()["sessionId"] == latest_id
    assert _message_count(latest_id) == before_messages
    assert login.get_json()["messages"][-1]["content"] == "Latest unfinished session."


def test_terminal_sessions_are_not_resumed_as_unfinished_drafts(client: FlaskClient) -> None:
    olivia = _patient_by_email("olivia.carter.phase2.demo@example.com")
    terminal_ids = {
        _create_chat_session(
            olivia.id,
            ChatState.CONFIRMED,
            datetime(2026, 7, 27, 12, 0, tzinfo=UTC),
            "Confirmed historical session.",
            completed=True,
        ),
        _create_chat_session(
            olivia.id,
            ChatState.ESCALATED,
            datetime(2026, 7, 27, 13, 0, tzinfo=UTC),
            "Emergency historical session.",
            completed=True,
            escalation_type="emergency",
        ),
        _create_chat_session(
            olivia.id,
            ChatState.CARE_TEAM_HANDOFF,
            datetime(2026, 7, 27, 14, 0, tzinfo=UTC),
            "Handoff historical session.",
            completed=True,
            escalation_type="care_team_handoff",
        ),
    }

    login = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )

    assert login.status_code == 201
    assert login.get_json()["sessionId"] not in terminal_ids
    assert login.get_json()["status"] == ChatState.COLLECTING_INTAKE


def test_patient_cannot_resume_another_patient_session_even_if_session_id_is_remembered(
    client: FlaskClient,
) -> None:
    other = _create_patient("Other", "Patient", "other.patient@example.test", "+18055559055")
    other_session_id = _create_chat_session(
        other.id,
        ChatState.COLLECTING_INTAKE,
        datetime(2026, 7, 27, 12, 0, tzinfo=UTC),
        "Other patient unfinished session.",
    )
    _sign_in_olivia(client)
    with client.session_transaction() as browser_session:
        browser_session["patient_chat_session_ids"] = [other_session_id]

    unauthorized = client.get(f"/api/chat/sessions/{other_session_id}")

    assert unauthorized.status_code == 401
    assert unauthorized.get_json()["error"]["code"] == "UNAUTHORIZED"


def test_profile_email_update_changes_future_login_identifier_without_changing_password_hash(
    client: FlaskClient,
) -> None:
    _sign_in_olivia(client)
    before_hash = _patient_by_email("olivia.carter.phase2.demo@example.com").password_hash
    updated = client.patch(
        "/api/patient/profile",
        json={"email": "olivia.updated@example.test", "phone": "+18055550187"},
    )

    logout = client.post("/api/patient/logout")
    old_email = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )
    new_email = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.updated@example.test", "password": "Patient!2026"},
    )

    assert updated.status_code == 200
    assert logout.status_code == 200
    assert old_email.status_code == 401
    assert old_email.get_json()["error"]["message"] == GENERIC_LOGIN_FAILURE
    assert new_email.status_code in {200, 201}
    assert _patient_by_email("olivia.updated@example.test").password_hash == before_hash
    assert _patient_count("olivia.carter.phase2.demo@example.com") == 0


def _new_patient_payload() -> dict[str, str]:
    return {
        "patientMode": "new",
        "firstName": "Jose",
        "lastName": "Rivera",
        "dateOfBirth": "1994-05-04",
        "phone": "805-555-4001",
        "email": "jose.rivera@example.test",
        "password": NEW_PATIENT_PASSWORD,
        "confirmPassword": NEW_PATIENT_PASSWORD,
        "insuranceProvider": "Acme Health",
    }


def _sign_in_olivia(client: FlaskClient) -> int:
    response = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )
    assert response.status_code in {200, 201}, response.get_json()
    return int(response.get_json()["sessionId"])


def _patient_by_email(email: str) -> Patient:
    session = get_session_factory()()
    try:
        patient = session.scalar(select(Patient).where(Patient.email == email))
        assert patient is not None
        session.expunge(patient)
        return patient
    finally:
        session.close()


def _patient_count(email: str) -> int:
    session = get_session_factory()()
    try:
        return int(session.scalar(select(func.count(Patient.id)).where(Patient.email == email)) or 0)
    finally:
        session.close()


def _chat_session_exists(session_id: int) -> bool:
    session = get_session_factory()()
    try:
        return session.get(ChatSession, session_id) is not None
    finally:
        session.close()


def _chat_session_patient_id(session_id: int) -> int | None:
    session = get_session_factory()()
    try:
        chat_session = session.get(ChatSession, session_id)
        return chat_session.patient_id if chat_session else None
    finally:
        session.close()


def _message_count(session_id: int) -> int:
    session = get_session_factory()()
    try:
        return int(session.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)) or 0)
    finally:
        session.close()


def _create_patient(first_name: str, last_name: str, email: str, phone: str) -> Patient:
    session = get_session_factory()()
    try:
        patient = Patient(
            first_name=first_name,
            last_name=last_name,
            date_of_birth=datetime(1990, 1, 1, tzinfo=UTC).date(),
            phone=phone,
            email=email,
            password_hash=None,
            insurance_provider=None,
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)
        session.expunge(patient)
        return patient
    finally:
        session.close()


def _create_chat_session(
    patient_id: int,
    status: str,
    updated_at: datetime,
    assistant_message: str,
    *,
    completed: bool = False,
    escalation_type: str | None = None,
    routing_result: dict[str, Any] | None = None,
) -> int:
    session = get_session_factory()()
    try:
        chat_session = ChatSession(
            patient_id=patient_id,
            status=status,
            current_step=_step_for_status(status),
            collected_data_json={
                "patient_type": "returning",
                "full_name": "Olivia Carter",
                "date_of_birth": "1993-06-12",
                "phone": "+18055550187",
                "email": "olivia.carter.phase2.demo@example.com",
            },
            routing_result_json=routing_result,
            escalation_type=escalation_type,
            escalation_reason="Historical terminal session." if escalation_type else None,
            completed_at=updated_at if completed else None,
            created_at=updated_at - timedelta(minutes=5),
            updated_at=updated_at,
        )
        session.add(chat_session)
        session.flush()
        session.add(
            ChatMessage(
                session_id=chat_session.id,
                role="assistant",
                content=assistant_message,
                sequence_number=1,
                metadata_json=None,
                created_at=updated_at - timedelta(minutes=4),
            )
        )
        session.commit()
        return chat_session.id
    finally:
        session.close()


def _step_for_status(status: str) -> str:
    if status == ChatState.ROUTING:
        return ChatStep.ROUTING_RECOMMENDATION
    if status == ChatState.SELECTING_APPOINTMENT:
        return ChatStep.SLOT_SELECTION
    if status == ChatState.CONFIRMED:
        return ChatStep.BOOKING_CONFIRMATION
    return ChatStep.COLLECT_INTAKE
