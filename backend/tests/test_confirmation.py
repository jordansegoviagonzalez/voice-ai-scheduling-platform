from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask.testing import FlaskClient
from sqlalchemy import select

from app.extensions import get_session_factory
from app.models import BookingConfirmation


def _new_patient_and_call(client: FlaskClient) -> tuple[dict[str, object], dict[str, object]]:
    patient = client.post(
        "/api/v1/patients",
        json={
            "first_name": "Casey",
            "last_name": "Confirm",
            "phone": "+18055550944",
            "date_of_birth": "1984-04-14",
        },
    ).get_json()["patient"]
    call = client.post("/api/v1/calls", json={"caller_phone": "+18055550944", "patient_id": patient["id"]}).get_json()[
        "call"
    ]
    return patient, call


def _first_slot(client: FlaskClient) -> int:
    routing = client.post(
        "/api/v1/routing/recommendations",
        json={"patient_status": "NEW", "body_part": "Shoulder", "issue_type": "Fracture"},
    ).get_json()
    return int(routing["recommended"]["available_slots"][0]["id"])


def test_confirmation_persists_selected_booking_details(client: FlaskClient) -> None:
    patient, call = _new_patient_and_call(client)
    slot_id = _first_slot(client)
    response = client.post(
        "/api/v1/booking-confirmations",
        json={
            "call_id": call["id"],
            "patient_id": patient["id"],
            "slot_id": slot_id,
            "body_part": "Shoulder",
            "issue_type": "Fracture",
        },
    )
    assert response.status_code == 201, response.get_json()
    confirmation = response.get_json()["confirmation"]
    assert confirmation["slot_id"] == slot_id
    assert confirmation["patient_id"] == patient["id"]
    assert confirmation["body_part"] == "Shoulder"
    assert confirmation["issue_type"] == "Fracture"
    assert confirmation["doctor"]["full_name"].startswith("Dr.")
    assert confirmation["location"]["name"]


def test_booking_rejects_confirmation_mismatch(client: FlaskClient) -> None:
    patient, call = _new_patient_and_call(client)
    slot_id = _first_slot(client)
    confirmation = client.post(
        "/api/v1/booking-confirmations",
        json={
            "call_id": call["id"],
            "patient_id": patient["id"],
            "slot_id": slot_id,
            "body_part": "Shoulder",
            "issue_type": "Fracture",
        },
    ).get_json()["confirmation"]
    response = client.post(
        "/api/v1/appointments",
        json={
            "call_id": call["id"],
            "patient_id": patient["id"],
            "slot_id": slot_id,
            "body_part": "Shoulder",
            "issue_type": "General",
            "confirmation_token": confirmation["confirmation_token"],
        },
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "BOOKING_CONFIRMATION_MISMATCH"


def test_booking_rejects_stale_confirmation(client: FlaskClient) -> None:
    patient, call = _new_patient_and_call(client)
    slot_id = _first_slot(client)
    confirmation = client.post(
        "/api/v1/booking-confirmations",
        json={
            "call_id": call["id"],
            "patient_id": patient["id"],
            "slot_id": slot_id,
            "body_part": "Shoulder",
            "issue_type": "Fracture",
        },
    ).get_json()["confirmation"]
    session = get_session_factory()()
    row = session.scalar(
        select(BookingConfirmation).where(BookingConfirmation.confirmation_token == confirmation["confirmation_token"])
    )
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    session.commit()
    session.close()

    response = client.post(
        "/api/v1/appointments",
        json={
            "call_id": call["id"],
            "patient_id": patient["id"],
            "slot_id": slot_id,
            "body_part": "Shoulder",
            "issue_type": "Fracture",
            "confirmation_token": confirmation["confirmation_token"],
        },
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "BOOKING_CONFIRMATION_STALE"


def test_booking_confirmation_token_is_single_use(client: FlaskClient) -> None:
    patient, call = _new_patient_and_call(client)
    slot_id = _first_slot(client)
    confirmation = client.post(
        "/api/v1/booking-confirmations",
        json={
            "call_id": call["id"],
            "patient_id": patient["id"],
            "slot_id": slot_id,
            "body_part": "Shoulder",
            "issue_type": "Fracture",
        },
    ).get_json()["confirmation"]
    assert len(confirmation["confirmation_token"]) >= 40
    payload = {
        "call_id": call["id"],
        "patient_id": patient["id"],
        "slot_id": slot_id,
        "body_part": "Shoulder",
        "issue_type": "Fracture",
        "confirmation_token": confirmation["confirmation_token"],
    }

    first = client.post("/api/v1/appointments", json=payload)
    second = client.post("/api/v1/appointments", json=payload)

    assert first.status_code == 201, first.get_json()
    assert second.status_code == 409
    assert second.get_json()["error"]["code"] == "BOOKING_CONFIRMATION_USED"
