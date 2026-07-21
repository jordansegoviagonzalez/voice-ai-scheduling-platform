from __future__ import annotations

import hashlib
import hmac
import json

from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import func, select

from app.extensions import get_session_factory
from app.integrations.vogent import security
from app.models import Appointment, Call


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

    session = get_session_factory()()
    count = session.scalar(select(func.count(Appointment.id)).where(Appointment.slot_id == slot_id))
    session.close()
    assert count == 1
