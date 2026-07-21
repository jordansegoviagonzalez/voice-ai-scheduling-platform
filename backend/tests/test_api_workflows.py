from __future__ import annotations

from flask.testing import FlaskClient


def _confirm_slot(
    client: FlaskClient,
    *,
    call_id: int,
    patient_id: int,
    slot_id: int,
    body_part: str,
    issue_type: str,
) -> str:
    confirmed = client.post(
        "/api/v1/booking-confirmations",
        json={
            "call_id": call_id,
            "patient_id": patient_id,
            "slot_id": slot_id,
            "body_part": body_part,
            "issue_type": issue_type,
        },
    )
    assert confirmed.status_code == 201, confirmed.get_json()
    return str(confirmed.get_json()["confirmation"]["confirmation_token"])


def test_patient_lookup_creation_and_duplicate_handling(client: FlaskClient) -> None:
    payload = {
        "first_name": "Alex",
        "last_name": "Morgan",
        "phone": "805-555-0199",
        "date_of_birth": "1992-08-14",
    }
    first = client.post("/api/v1/patients", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/patients", json=payload)
    assert second.status_code == 200
    assert second.get_json()["created"] is False
    lookup = client.post(
        "/api/v1/patients/lookup",
        json={"phone": payload["phone"], "date_of_birth": payload["date_of_birth"]},
    )
    assert lookup.get_json()["found"] is True


def test_protocol_contains_exact_apostrophe(client: FlaskClient) -> None:
    doctors = client.get("/api/v1/doctors").get_json()["doctors"]
    assert any(item["last_name"] == "O'Brien" for item in doctors)


def test_simulator_creates_call_transcript_routing_and_booking(client: FlaskClient) -> None:
    preview = client.post(
        "/api/v1/simulator/preview",
        json={
            "caller_phone": "+18055550199",
            "first_name": "Taylor",
            "last_name": "Reed",
            "date_of_birth": "1995-02-04",
            "patient_status": "NEW",
            "body_part": "Shoulder",
            "issue_type": "Fracture",
        },
    )
    assert preview.status_code == 201, preview.get_json()
    data = preview.get_json()
    assert len(data["call"]["transcript"]) >= 4
    assert data["call"]["routing_decisions"]
    slot_id = data["routing"]["recommended"]["available_slots"][0]["id"]
    confirmation_token = _confirm_slot(
        client,
        call_id=data["call"]["id"],
        patient_id=data["patient"]["id"],
        slot_id=slot_id,
        body_part="Shoulder",
        issue_type="Fracture",
    )
    booked = client.post(
        "/api/v1/simulator/book",
        json={
            "call_id": data["call"]["id"],
            "patient_id": data["patient"]["id"],
            "slot_id": slot_id,
            "body_part": "Shoulder",
            "issue_type": "Fracture",
            "confirmation_token": confirmation_token,
        },
    )
    assert booked.status_code == 201, booked.get_json()
    call = client.get(f"/api/v1/calls/{data['call']['id']}").get_json()["call"]
    assert call["status"] == "SCHEDULED"
    assert call["appointment"] is not None
    assert len(call["transcript"]) >= 6


def test_double_booking_conflict_through_api(client: FlaskClient) -> None:
    patient_a = client.post(
        "/api/v1/patients",
        json={
            "first_name": "One",
            "last_name": "Patient",
            "phone": "+18055550701",
            "date_of_birth": "1980-01-01",
        },
    ).get_json()["patient"]
    patient_b = client.post(
        "/api/v1/patients",
        json={
            "first_name": "Two",
            "last_name": "Patient",
            "phone": "+18055550702",
            "date_of_birth": "1981-01-01",
        },
    ).get_json()["patient"]
    routing = client.post(
        "/api/v1/routing/recommendations",
        json={"patient_status": "NEW", "body_part": "Shoulder", "issue_type": "Fracture"},
    ).get_json()
    slot_id = routing["recommended"]["available_slots"][0]["id"]
    call_a = client.post(
        "/api/v1/calls",
        json={"caller_phone": "+18055550701", "patient_id": patient_a["id"]},
    ).get_json()["call"]
    call_b = client.post(
        "/api/v1/calls",
        json={"caller_phone": "+18055550702", "patient_id": patient_b["id"]},
    ).get_json()["call"]
    token_a = _confirm_slot(
        client,
        call_id=call_a["id"],
        patient_id=patient_a["id"],
        slot_id=slot_id,
        body_part="Shoulder",
        issue_type="Fracture",
    )
    token_b = _confirm_slot(
        client,
        call_id=call_b["id"],
        patient_id=patient_b["id"],
        slot_id=slot_id,
        body_part="Shoulder",
        issue_type="Fracture",
    )
    payload = {"slot_id": slot_id, "body_part": "Shoulder", "issue_type": "Fracture"}
    first = client.post(
        "/api/v1/appointments",
        json={**payload, "patient_id": patient_a["id"], "call_id": call_a["id"], "confirmation_token": token_a},
    )
    second = client.post(
        "/api/v1/appointments",
        json={**payload, "patient_id": patient_b["id"], "call_id": call_b["id"], "confirmation_token": token_b},
    )
    assert first.status_code == 201
    assert second.status_code == 409


def test_booking_requires_durable_caller_confirmation(client: FlaskClient) -> None:
    patient = client.post(
        "/api/v1/patients",
        json={
            "first_name": "Missing",
            "last_name": "Confirm",
            "phone": "+18055550703",
            "date_of_birth": "1982-01-01",
        },
    ).get_json()["patient"]
    routing = client.post(
        "/api/v1/routing/recommendations",
        json={"patient_status": "NEW", "body_part": "Shoulder", "issue_type": "Fracture"},
    ).get_json()
    response = client.post(
        "/api/v1/appointments",
        json={
            "patient_id": patient["id"],
            "slot_id": routing["recommended"]["available_slots"][0]["id"],
            "body_part": "Shoulder",
            "issue_type": "Fracture",
        },
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_call_creation_and_transcript_persistence(client: FlaskClient) -> None:
    created = client.post("/api/v1/calls", json={"caller_phone": "+18055550888"})
    call_id = created.get_json()["call"]["id"]
    turn = client.post(
        f"/api/v1/calls/{call_id}/transcript-turns",
        json={"speaker": "HUMAN", "text": "I need an appointment."},
    )
    assert turn.status_code == 201
    detail = client.get(f"/api/v1/calls/{call_id}").get_json()["call"]
    assert detail["transcript"][0]["text"] == "I need an appointment."


def test_dashboard_analytics_are_database_derived(client: FlaskClient) -> None:
    overview = client.get("/api/v1/dashboard/overview")
    assert overview.status_code == 200
    data = overview.get_json()
    assert data["metrics"]["total_calls"] >= 4
    assert sum(item["count"] for item in data["outcomes"]) == data["metrics"]["total_calls"]
    statuses = {item["id"]: item for item in data["integration_statuses"]}
    assert statuses["openai_gpt_5_2"]["status_label"] == "Not configured"
    assert statuses["vogent_voice_agent"]["status_label"] == "Awaiting credentials"
