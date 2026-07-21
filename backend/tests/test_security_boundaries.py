from __future__ import annotations

import hashlib
import hmac
import json

from flask import Flask
from flask.testing import FlaskClient


def _signed_post(client: FlaskClient, *, payload: dict[str, object], secret: str):  # type: ignore[no-untyped-def]
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return client.post(
        "/api/v1/vogent/webhooks",
        data=body,
        headers={"Content-Type": "application/json", "X-Elto-Signature": signature},
    )


def test_request_body_limit_rejects_oversized_payload(app: Flask, client: FlaskClient) -> None:
    app.config["MAX_CONTENT_LENGTH"] = 128
    response = client.post(
        "/api/v1/conversation/interpret",
        data=json.dumps({"raw_user_text": "x" * 256}),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.get_json()["error"]["code"] in {"REQUEST_ENTITY_TOO_LARGE", "FIELD_TOO_LONG"}


def test_field_limit_rejects_oversized_patient_name(client: FlaskClient) -> None:
    response = client.post(
        "/api/v1/patients",
        json={
            "first_name": "A" * 101,
            "last_name": "Patient",
            "phone": "+18055551111",
            "date_of_birth": "1990-01-01",
        },
    )

    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "FIELD_TOO_LONG"


def test_live_conversation_without_key_fails_closed(client: FlaskClient) -> None:
    response = client.post(
        "/api/v1/conversation/interpret",
        json={"raw_user_text": "I am a new patient with shoulder pain."},
    )

    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "OPENAI_API_KEY_MISSING"


def test_database_backed_rate_limit_returns_stable_429(app: Flask, client: FlaskClient) -> None:
    app.config["RATE_LIMIT_ENABLED"] = True
    app.config["RATE_LIMIT_MAX_REQUESTS"] = 2
    app.config["RATE_LIMIT_WINDOW_SECONDS"] = 60

    payload = {
        "first_name": "Rate",
        "last_name": "Limited",
        "phone": "+18055552222",
        "date_of_birth": "1990-01-01",
    }

    assert client.post("/api/v1/patients", json=payload).status_code == 201
    assert client.post("/api/v1/patients", json=payload).status_code == 200
    blocked = client.post("/api/v1/patients", json=payload)

    assert blocked.status_code == 429
    assert blocked.get_json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_vogent_transcript_turn_limit_rejects_oversized_text(app: Flask, client: FlaskClient) -> None:
    secret = "test-webhook-secret"
    app.config["VOGENT_WEBHOOK_SECRET"] = secret
    app.config["TRANSCRIPT_TURN_MAX_LENGTH"] = 12

    inbound = _signed_post(
        client,
        secret=secret,
        payload={"event": "dial.inbound", "payload": {"dial_id": "dial-limit-001", "source_number": "+18055553333"}},
    )
    assert inbound.status_code == 200

    transcript = _signed_post(
        client,
        secret=secret,
        payload={
            "event": "dial.transcript",
            "payload": {
                "dial_id": "dial-limit-001",
                "transcript": [{"speaker": "USER", "text": "this transcript turn is too large"}],
            },
        },
    )

    assert transcript.status_code == 413
    assert transcript.get_json()["error"]["code"] == "FIELD_TOO_LONG"
