from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, date, datetime, timedelta

from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import func, select, text

from app.extensions import get_session_factory
from app.integrations.vogent import security
from app.models import Appointment, Call, Doctor, DoctorLocation, Location, Organization, Patient, Slot


def _signed_post(client: FlaskClient, *, payload: dict[str, object], secret: str):  # type: ignore[no-untyped-def]
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return client.post(
        "/api/v1/vogent/webhooks",
        data=body,
        headers={"Content-Type": "application/json", "X-Elto-Signature": signature},
    )


def test_function_secret_uses_constant_time_compare(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str]] = []

    def fake_compare(left: str, right: str) -> bool:
        calls.append((left, right))
        return left == right

    monkeypatch.setattr(security.hmac, "compare_digest", fake_compare)
    assert security.verify_shared_secret("secret", "secret") is True
    assert calls == [("secret", "secret")]


def test_vogent_webhook_rejects_invalid_signature(app: Flask, client: FlaskClient) -> None:
    app.config["VOGENT_WEBHOOK_SECRET"] = "test-webhook-secret"
    response = client.post(
        "/api/v1/vogent/webhooks",
        json={"event": "dial.inbound", "payload": {"dial_id": "dial-invalid", "source_number": "+18055550000"}},
        headers={"X-Elto-Signature": "invalid"},
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "INVALID_WEBHOOK_SIGNATURE"


def test_vogent_inbound_and_transcript_webhooks_persist_call(app: Flask, client: FlaskClient) -> None:
    secret = "test-webhook-secret"
    app.config["VOGENT_WEBHOOK_SECRET"] = secret

    inbound = _signed_post(
        client,
        secret=secret,
        payload={
            "event": "dial.inbound",
            "payload": {"dial_id": "dial-qa-001", "source_number": "+18055550001"},
        },
    )
    assert inbound.status_code == 200
    internal_call_id = int(inbound.get_json()["call_agent_input"]["internal_call_id"])
    duplicate_inbound = _signed_post(
        client,
        secret=secret,
        payload={
            "event": "dial.inbound",
            "payload": {"dial_id": "dial-qa-001", "source_number": "+18055550001"},
        },
    )
    assert duplicate_inbound.status_code == 200
    assert duplicate_inbound.get_json()["duplicate"] is True
    assert duplicate_inbound.get_json()["call_agent_input"]["internal_call_id"] == str(internal_call_id)

    transcript = _signed_post(
        client,
        secret=secret,
        payload={
            "event": "dial.transcript",
            "payload": {
                "dial_id": "dial-qa-001",
                "transcript": [
                    {"speaker": "AI", "text": "How can I help?"},
                    {"speaker": "USER", "text": "I need a knee appointment."},
                ],
            },
        },
    )
    assert transcript.status_code == 200
    duplicate_transcript = _signed_post(
        client,
        secret=secret,
        payload={
            "event": "dial.transcript",
            "payload": {
                "dial_id": "dial-qa-001",
                "transcript": [
                    {"speaker": "AI", "text": "How can I help?"},
                    {"speaker": "USER", "text": "I need a knee appointment."},
                ],
            },
        },
    )
    assert duplicate_transcript.status_code == 200
    assert duplicate_transcript.get_json()["duplicate"] is True

    detail = client.get(f"/api/v1/calls/{internal_call_id}")
    assert detail.status_code == 200
    turns = detail.get_json()["call"]["transcript"]
    assert [turn["speaker"] for turn in turns] == ["AI", "HUMAN"]
    assert turns[1]["text"] == "I need a knee appointment."


def test_vogent_stale_status_cannot_overwrite_terminal_call(app: Flask, client: FlaskClient) -> None:
    secret = "test-webhook-secret"
    app.config["VOGENT_WEBHOOK_SECRET"] = secret
    created = client.post(
        "/api/v1/calls",
        json={"external_call_id": "dial-terminal-001", "caller_phone": "+18055550002", "status": "SCHEDULED"},
    )
    call_id = created.get_json()["call"]["id"]
    failed = _signed_post(
        client,
        secret=secret,
        payload={
            "event": "dial.updated",
            "payload": {"dial_id": "dial-terminal-001", "status": "failed"},
        },
    )
    assert failed.status_code == 200
    detail = client.get(f"/api/v1/calls/{call_id}").get_json()["call"]
    assert detail["status"] == "SCHEDULED"


def test_vogent_terminal_state_transitions_are_table_driven(app: Flask, client: FlaskClient) -> None:
    secret = "test-webhook-secret"
    app.config["VOGENT_WEBHOOK_SECRET"] = secret
    cases = [
        ("SCHEDULED", "failed", "SCHEDULED"),
        ("REDIRECTED", "failed", "REDIRECTED"),
        ("FAILED", "canceled", "FAILED"),
        ("ABANDONED", "completed", "ABANDONED"),
        ("IN_PROGRESS", "failed", "FAILED"),
        ("IN_PROGRESS", "canceled", "ABANDONED"),
    ]
    for index, (initial, provider_status, expected) in enumerate(cases, start=1):
        created = client.post(
            "/api/v1/calls",
            json={
                "external_call_id": f"dial-transition-{index}",
                "caller_phone": f"+18055554{index:03d}",
                "status": initial,
            },
        )
        assert created.status_code == 201
        response = _signed_post(
            client,
            secret=secret,
            payload={
                "event": "dial.updated",
                "event_id": f"transition-{index}",
                "payload": {"dial_id": f"dial-transition-{index}", "status": provider_status},
            },
        )
        assert response.status_code == 200
        detail = client.get(f"/api/v1/calls/{created.get_json()['call']['id']}").get_json()["call"]
        assert detail["status"] == expected


def test_vogent_transcript_event_does_not_change_terminal_status(app: Flask, client: FlaskClient) -> None:
    secret = "test-webhook-secret"
    app.config["VOGENT_WEBHOOK_SECRET"] = secret
    created = client.post(
        "/api/v1/calls",
        json={"external_call_id": "dial-transcript-terminal", "caller_phone": "+18055554444", "status": "FAILED"},
    )
    assert created.status_code == 201
    response = _signed_post(
        client,
        secret=secret,
        payload={
            "event": "dial.transcript",
            "event_id": "terminal-transcript",
            "payload": {
                "dial_id": "dial-transcript-terminal",
                "transcript": [{"speaker": "USER", "text": "I disconnected."}],
            },
        },
    )
    assert response.status_code == 200
    detail = client.get(f"/api/v1/calls/{created.get_json()['call']['id']}").get_json()["call"]
    assert detail["status"] == "FAILED"
    assert detail["transcript"][0]["text"] == "I disconnected."


def test_vogent_duplicate_completion_event_is_idempotent(app: Flask, client: FlaskClient) -> None:
    secret = "test-webhook-secret"
    app.config["VOGENT_WEBHOOK_SECRET"] = secret
    client.post(
        "/api/v1/calls",
        json={"external_call_id": "dial-duplicate-complete", "caller_phone": "+18055554545", "status": "IN_PROGRESS"},
    )
    payload = {
        "event": "dial.updated",
        "event_id": "complete-once",
        "payload": {"dial_id": "dial-duplicate-complete", "status": "failed"},
    }
    first = _signed_post(client, secret=secret, payload=payload)
    second = _signed_post(client, secret=secret, payload=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()["duplicate"] is True

    session = get_session_factory()()
    call = session.scalar(select(Call).where(Call.external_call_id == "dial-duplicate-complete"))
    session.close()
    assert call is not None
    assert call.status == "FAILED"


def test_vogent_duplicate_booking_returns_stored_result(app: Flask, client: FlaskClient) -> None:
    app.config["VOGENT_FUNCTION_SECRET"] = "function-secret"
    headers = {"X-Vogent-Function-Secret": "function-secret", "Idempotency-Key": "book-once"}
    patient = client.post(
        "/api/v1/patients",
        json={
            "first_name": "Vogent",
            "last_name": "Caller",
            "phone": "+18055550003",
            "date_of_birth": "1990-03-03",
        },
    ).get_json()["patient"]
    call = client.post(
        "/api/v1/calls",
        json={"caller_phone": "+18055550003", "patient_id": patient["id"]},
    ).get_json()["call"]
    routing = client.post(
        "/api/v1/routing/recommendations",
        json={"patient_status": "NEW", "body_part": "Shoulder", "issue_type": "Fracture"},
    ).get_json()
    slot_id = routing["recommended"]["available_slots"][0]["id"]
    confirmed = client.post(
        "/api/v1/vogent/functions/confirm-slot",
        json={
            "call_id": call["id"],
            "patient_id": patient["id"],
            "slot_id": slot_id,
            "body_part": "Shoulder",
            "issue_type": "Fracture",
        },
        headers={"X-Vogent-Function-Secret": "function-secret", "Idempotency-Key": "confirm-once"},
    )
    assert confirmed.status_code == 201, confirmed.get_json()
    payload = {
        "call_id": call["id"],
        "patient_id": patient["id"],
        "slot_id": slot_id,
        "body_part": "Shoulder",
        "issue_type": "Fracture",
        "confirmation_token": confirmed.get_json()["confirmation_token"],
    }
    first = client.post("/api/v1/vogent/functions/book-appointment", json=payload, headers=headers)
    duplicate = client.post("/api/v1/vogent/functions/book-appointment", json=payload, headers=headers)
    assert first.status_code == 201, first.get_json()
    assert duplicate.status_code == 201, duplicate.get_json()
    assert duplicate.get_json() == first.get_json()

    # Assert location address fields are included in confirmation
    confirmed_data = confirmed.get_json()
    assert "address_line1" in confirmed_data
    assert "city" in confirmed_data

    # Assert location address fields are included in booking
    booking_data = first.get_json()
    assert "address_line1" in booking_data
    assert "city" in booking_data

    session = get_session_factory()()
    count = session.scalar(select(func.count(Appointment.id)).where(Appointment.slot_id == slot_id))
    session.close()
    assert count == 1


def test_vogent_patient_lookup_accepts_spoken_dob_and_spoken_phone(client: FlaskClient) -> None:
    response = client.post(
        "/api/v1/vogent/functions/patient-lookup",
        json={"phone": "8 0 5 5 5 5 0 1 0 1", "date_of_birth": "April 12 1990"},
    )
    assert response.status_code == 200
    assert response.get_json() == {"found": True, "patient_id": 1, "patient_name": "Sarah Johnson"}


def test_vogent_patient_lookup_rejects_unparseable_dob(client: FlaskClient) -> None:
    response = client.post(
        "/api/v1/vogent/functions/patient-lookup",
        json={"phone": "8055550101", "date_of_birth": "not a real birthday"},
    )
    assert response.status_code == 422
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "date_of_birth could not be parsed."


def test_vogent_invalid_org_slug_fails_loudly_without_fallback(client: FlaskClient) -> None:
    response = client.post(
        "/api/v1/organizations/slug/does-not-exist/vogent/functions/patient-lookup",
        json={"phone": "555-0101", "date_of_birth": "1990-01-01"},
    )
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["error"]["code"] == "ORGANIZATION_NOT_FOUND"
    serialized = json.dumps(payload)
    assert "default-orthopedics" not in serialized
    assert "client_links" not in serialized
    assert "voice" not in serialized


def test_vogent_wrong_org_slot_booking_fails(app: Flask, client: FlaskClient) -> None:
    with app.app_context():
        session = get_session_factory()()
        org1 = session.scalar(text("SELECT id FROM organizations WHERE slug = 'default-orthopedics'"))
        org2 = Organization(
            name="Other Org",
            slug="other-org",
            status="ACTIVE",
            timezone="America/Los_Angeles",
            business_hours={"monday": [{"open": "08:00", "close": "17:00"}]},
        )
        session.add(org2)
        session.flush()
        doc2 = Doctor(
            organization_id=org2.id,
            first_name="Other",
            last_name="Doc",
            accepts_new_patients=True,
            active=True,
        )
        loc2 = Location(organization_id=org2.id, name="Other Clinic", code="OTHER")
        session.add_all([doc2, loc2])
        session.flush()
        session.add(DoctorLocation(doctor_id=doc2.id, location_id=loc2.id))

        tomorrow = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
        if tomorrow.weekday() > 4:
            tomorrow += timedelta(days=2)

        slot2 = Slot(
            organization_id=org2.id,
            doctor_id=doc2.id,
            location_id=loc2.id,
            starts_at=tomorrow,
            ends_at=tomorrow + timedelta(minutes=30),
            status="OPEN",
        )
        pat1 = Patient(
            organization_id=org1,
            first_name="Pat",
            last_name="One",
            date_of_birth=date(1990, 1, 1),
            phone="5550101",
        )
        session.add_all([slot2, pat1])
        session.commit()

        slot2_id = slot2.id
        pat1_id = pat1.id
        session.close()

    response = client.post(
        "/api/v1/organizations/slug/default-orthopedics/vogent/functions/book-appointment",
        json={
            "patient_id": pat1_id,
            "slot_id": slot2_id,
            "body_part": "knee",
            "issue_type": "pain",
            "confirmation_token": "token123",
        },
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "ORGANIZATION_CONTEXT_MISMATCH"
