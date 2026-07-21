from __future__ import annotations

from flask.testing import FlaskClient


def route(client: FlaskClient, **overrides):  # type: ignore[no-untyped-def]
    payload = {
        "patient_status": "NEW",
        "body_part": "Knee",
        "issue_type": "Fracture",
        **overrides,
    }
    response = client.post("/api/v1/routing/recommendations", json=payload)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def names(items):  # type: ignore[no-untyped-def]
    return {item["doctor"]["last_name"] for item in items}


def test_scenario_a_new_patient_knee_fracture(client: FlaskClient) -> None:
    result = route(client)
    assert {"Walsh", "Vasquez"} <= names(result["eligible_doctors"])
    assert {"Chen", "Torres", "Brooks"} <= names(result["rejected_doctors"])


def test_scenario_b_new_patient_general_spine(client: FlaskClient) -> None:
    result = route(client, body_part="Spine", issue_type="General")
    assert "Mendez" in names(result["eligible_doctors"])
    assert {"Patel", "Reed", "O'Brien"} <= names(result["rejected_doctors"])


def test_scenario_c_returning_patient_previously_seen_by_patel(
    client: FlaskClient, ids: dict[str, dict[str, int]]
) -> None:
    lookup = client.post(
        "/api/v1/patients/lookup",
        json={"phone": "+18055550105", "date_of_birth": "1982-11-06"},
    ).get_json()
    result = route(
        client,
        patient_id=lookup["patient"]["id"],
        patient_status="RETURNING",
        body_part="Spine",
        issue_type="General",
        preferred_doctor_id=ids["doctors"]["Patel"],
    )
    assert "Patel" in names(result["eligible_doctors"])
    assert result["recommended"]["doctor"]["last_name"] == "Patel"


def test_returning_facility_patient_without_doctor_history_is_rejected(
    client: FlaskClient, ids: dict[str, dict[str, int]]
) -> None:
    lookup = client.post(
        "/api/v1/patients/lookup",
        json={"phone": "+18055550101", "date_of_birth": "1990-04-12"},
    ).get_json()
    result = route(
        client,
        patient_id=lookup["patient"]["id"],
        patient_status="RETURNING",
        body_part="Spine",
        issue_type="General",
        preferred_doctor_id=ids["doctors"]["Patel"],
    )
    patel = next(item for item in result["rejected_doctors"] if item["doctor"]["last_name"] == "Patel")
    assert patel["reason_code"] == "PATIENT_HAS_NO_HISTORY_WITH_DOCTOR"


def test_scenario_d_hand_wrist_sports_injury(client: FlaskClient) -> None:
    result = route(client, body_part="Hand/Wrist", issue_type="Sports Medicine")
    assert "Kim" in names(result["eligible_doctors"])
    assert {"Reed", "Nguyen"} <= names(result["rejected_doctors"])


def test_scenario_e_shoulder_fracture(client: FlaskClient) -> None:
    result = route(client, body_part="Shoulder", issue_type="Fracture")
    exact = [item for item in result["eligible_doctors"] if item["available_slots"]]
    assert {item["doctor"]["last_name"] for item in exact} == {"Vasquez"}


def test_scenario_f_invalid_preferred_physician(client: FlaskClient, ids: dict[str, dict[str, int]]) -> None:
    result = route(client, preferred_doctor_id=ids["doctors"]["Chen"])
    chen = next(item for item in result["rejected_doctors"] if item["doctor"]["last_name"] == "Chen")
    assert chen["reason_code"] == "ISSUE_TYPE_NOT_SUPPORTED"
    assert "not" in chen["reason"]
    assert {"Walsh", "Vasquez"} <= names(result["eligible_doctors"])


def test_scenario_g_fallback_when_first_valid_doctor_has_no_slots(client: FlaskClient) -> None:
    result = route(client)
    walsh = next(item for item in result["eligible_doctors"] if item["doctor"]["last_name"] == "Walsh")
    assert walsh["available_slots"] == []
    assert result["recommended"]["doctor"]["last_name"] == "Vasquez"
    assert result["fallback_explanation"] is not None


def test_scenario_h_preferred_location_unavailable(client: FlaskClient, ids: dict[str, dict[str, int]]) -> None:
    result = route(client, preferred_location_id=ids["locations"]["NORTH"])
    assert result["recommended"]["doctor"]["last_name"] == "Vasquez"
    assert result["recommended"]["preferred_location_match"] is False
    assert "different location" in result["caller_safe_summary"].lower()


def test_general_does_not_match_specific_categories(client: FlaskClient) -> None:
    result = route(client, body_part="Hip", issue_type="Fracture")
    torres = next(item for item in result["rejected_doctors"] if item["doctor"]["last_name"] == "Torres")
    assert torres["reason_code"] == "ISSUE_TYPE_NOT_SUPPORTED"


def test_ranking_is_stable(client: FlaskClient) -> None:
    first = route(client, body_part="Hip", issue_type="Joint Replacement")
    second = route(client, body_part="Hip", issue_type="Joint Replacement")
    assert [x["doctor"]["id"] for x in first["ranked_recommendations"]] == [
        x["doctor"]["id"] for x in second["ranked_recommendations"]
    ]
