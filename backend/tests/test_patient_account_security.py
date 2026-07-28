from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask.testing import FlaskClient
from sqlalchemy import func, select

from app.extensions import get_session_factory
from app.models import Appointment, ChatMessage, ChatSession, Patient


def test_authenticated_profile_returns_server_session_patient_only(client: FlaskClient) -> None:
    session_id = _sign_in_olivia(client)
    other_patient = client.post(
        "/api/v1/patients",
        json={
            "first_name": "Other",
            "last_name": "Patient",
            "phone": "+18055559001",
            "date_of_birth": "1991-01-01",
        },
    ).get_json()["patient"]

    response = client.get(f"/api/patient/profile?patientId={other_patient['id']}")

    assert response.status_code == 200
    payload = response.get_json()["patient"]
    assert payload["fullName"] == "Olivia Carter"
    assert payload["email"] == "olivia.carter.phase2.demo@example.com"
    assert payload["phone"] == "+18055550187"
    assert "id" not in payload
    assert "Encounter date" not in str(payload)
    assert session_id > 0


def test_unauthenticated_profile_request_returns_401(client: FlaskClient) -> None:
    response = client.get("/api/patient/profile")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "UNAUTHORIZED"


def test_profile_contact_update_persists_and_rejects_read_only_fields(client: FlaskClient) -> None:
    _sign_in_olivia(client)
    rejected = client.patch(
        "/api/patient/profile",
        json={"email": "olivia.updated@example.test", "phone": "805-555-9002", "firstName": "Changed"},
    )

    assert rejected.status_code == 422
    assert rejected.get_json()["error"]["field_errors"]["firstName"] == ["Read-only field"]

    updated = client.patch(
        "/api/patient/profile",
        json={"email": "OLIVIA.UPDATED@example.test", "phone": "(805) 555-9002"},
    )
    restored = client.get("/api/patient/profile")

    assert updated.status_code == 200, updated.get_json()
    assert updated.get_json()["patient"]["email"] == "olivia.updated@example.test"
    assert updated.get_json()["patient"]["phone"] == "+18055559002"
    assert restored.get_json()["patient"]["email"] == "olivia.updated@example.test"
    assert restored.get_json()["patient"]["phone"] == "+18055559002"


def test_invalid_profile_contact_update_is_rejected(client: FlaskClient) -> None:
    _sign_in_olivia(client)

    response = client.patch("/api/patient/profile", json={"email": "not-an-email", "phone": "bad"})

    assert response.status_code == 422
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "email" in body["error"]["field_errors"] or "phone" in body["error"]["field_errors"]


def test_patient_logout_invalidates_profile_and_chat_without_deleting_records(client: FlaskClient) -> None:
    session_id = _sign_in_olivia(client)
    before_counts = _record_counts()

    logout = client.post("/api/patient/logout")
    profile = client.get("/api/patient/profile")
    chat = client.get(f"/api/chat/sessions/{session_id}")
    after_counts = _record_counts()

    assert logout.status_code == 200
    assert profile.status_code == 401
    assert chat.status_code == 401
    assert before_counts == after_counts


def test_patient_idle_expiration_uses_configured_timeout(
    client: FlaskClient,
    monkeypatch,
) -> None:
    import app.services.session_security as session_security

    base_time = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(session_security, "utcnow", lambda: base_time)
    session_id = _sign_in_olivia(client)

    monkeypatch.setattr(session_security, "utcnow", lambda: base_time + timedelta(minutes=61))
    expired = client.get("/api/patient/profile")
    chat = client.get(f"/api/chat/sessions/{session_id}")

    assert expired.status_code == 401
    assert expired.get_json()["error"]["code"] == "SESSION_EXPIRED"
    assert chat.status_code == 401


def test_valid_patient_activity_refreshes_idle_timeout(client: FlaskClient, monkeypatch) -> None:
    import app.services.session_security as session_security

    base_time = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(session_security, "utcnow", lambda: base_time)
    _sign_in_olivia(client)

    monkeypatch.setattr(session_security, "utcnow", lambda: base_time + timedelta(minutes=59))
    active = client.get("/api/patient/profile")
    monkeypatch.setattr(session_security, "utcnow", lambda: base_time + timedelta(minutes=118))
    refreshed = client.get("/api/patient/profile")

    assert active.status_code == 200
    assert refreshed.status_code == 200


def test_admin_idle_expiration_and_patient_session_isolation(
    client: FlaskClient,
    monkeypatch,
) -> None:
    import app.services.session_security as session_security

    base_time = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(session_security, "utcnow", lambda: base_time)
    _sign_in_olivia(client)
    admin_login = client.post(
        "/api/auth/admin/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    patient_profile = client.get("/api/patient/profile")

    assert admin_login.status_code == 200
    assert patient_profile.status_code == 200

    client.post("/api/patient/logout")
    admin_still_active = client.get("/api/auth/admin/session")
    assert admin_still_active.status_code == 200

    monkeypatch.setattr(session_security, "utcnow", lambda: base_time + timedelta(minutes=61))
    expired = client.get("/api/auth/admin/session")

    assert expired.status_code == 401
    assert expired.get_json()["error"]["code"] == "SESSION_EXPIRED"


def _sign_in_olivia(client: FlaskClient) -> int:
    response = client.post(
        "/api/chat/sessions",
        json={"patientMode": "returning", "email": "olivia.carter.phase2.demo@example.com", "password": "Patient!2026"},
    )
    assert response.status_code in {200, 201}, response.get_json()
    return int(response.get_json()["sessionId"])


def _record_counts() -> tuple[int, int, int, int]:
    session = get_session_factory()()
    try:
        return (
            int(session.scalar(select(func.count(Patient.id))) or 0),
            int(session.scalar(select(func.count(ChatSession.id))) or 0),
            int(session.scalar(select(func.count(ChatMessage.id))) or 0),
            int(session.scalar(select(func.count(Appointment.id))) or 0),
        )
    finally:
        session.close()
