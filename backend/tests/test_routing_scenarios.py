from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from flask.testing import FlaskClient
from sqlalchemy import select

from app.extensions import get_session_factory
from app.models import Appointment, Doctor, Slot


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
    assert "Nguyen" in names(result["eligible_doctors"])
    assert "Reed" in names(result["rejected_doctors"])


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


def test_scenario_g_fallback_when_first_valid_doctor_has_no_slots(
    client: FlaskClient, ids: dict[str, dict[str, int]]
) -> None:
    first_weekday = _first_future_weekday()
    starts_after, ends_before = _local_day_bounds(first_weekday)
    result = route(
        client,
        body_part="Knee",
        issue_type="Sports Medicine",
        preferred_doctor_id=ids["doctors"]["Chen"],
        starts_after=starts_after.isoformat(),
        ends_before=ends_before.isoformat(),
    )
    chen = next(item for item in result["eligible_doctors"] if item["doctor"]["last_name"] == "Chen")
    assert chen["available_slots"] == []
    assert result["recommended"]["doctor"]["last_name"] == "Walsh"
    assert result["fallback_explanation"] is not None


def test_scenario_h_preferred_location_unavailable(client: FlaskClient, ids: dict[str, dict[str, int]]) -> None:
    result = route(
        client,
        body_part="Shoulder",
        issue_type="Fracture",
        preferred_location_id=ids["locations"]["NORTH"],
    )
    assert result["recommended"]["doctor"]["last_name"] == "Vasquez"
    assert result["recommended"]["preferred_location_match"] is False
    assert result["location_fallback"]["preferred_location"]["code"] == "NORTH"
    assert result["location_fallback"]["selected_location"]["code"] in {"MAIN", "WEST"}
    assert result["location_fallback"]["reason_code"] == "PREFERRED_LOCATION_UNAVAILABLE"
    assert "other clinic locations" in result["caller_safe_summary"].lower()


def test_preferred_location_exact_match_remains_first(client: FlaskClient, ids: dict[str, dict[str, int]]) -> None:
    result = route(
        client,
        body_part="Hip",
        issue_type="General",
        preferred_location_id=ids["locations"]["MAIN"],
    )
    assert result["recommended"]["doctor"]["last_name"] == "Torres"
    assert result["recommended"]["preferred_location_match"] is True
    assert result["recommended"]["routing_stage"] == "general_preferred_location"
    assert result["recommended"]["available_slots"][0]["location"]["code"] == "MAIN"
    assert result["location_fallback"] is None


def test_foot_ankle_general_prefers_alternative_location_when_main_has_no_match(
    client: FlaskClient, ids: dict[str, dict[str, int]]
) -> None:
    result = route(
        client,
        body_part="Foot/Ankle",
        issue_type="General",
        preferred_location_id=ids["locations"]["MAIN"],
    )

    assert result["recommended"]["doctor"]["last_name"] == "Walsh"
    assert result["recommended"]["available_slots"][0]["location"]["code"] == "NORTH"
    assert result["recommended"]["preferred_location_match"] is False
    assert result["recommended"]["routing_stage"] == "general_alternative_location"
    assert result["location_fallback"]["preferred_location"]["code"] == "MAIN"
    assert result["location_fallback"]["selected_location"]["code"] == "NORTH"
    assert result["location_fallback"]["reason_code"] == "PREFERRED_LOCATION_UNAVAILABLE"
    assert "Main Campus" in result["caller_safe_summary"]
    assert "No physician matches" not in result["caller_safe_summary"]
    ranked_names = [item["doctor"]["last_name"] for item in result["ranked_recommendations"]]
    assert ranked_names[:3] == ["Walsh", "Mendez", "Nguyen"]
    assert [item["is_general_orthopedics"] for item in result["ranked_recommendations"]].count(True) == 1


def test_foot_ankle_general_seed_coverage_has_two_specialists_and_one_general(
    client: FlaskClient,
) -> None:
    result = route(client, body_part="Foot/Ankle", issue_type="General")

    assert {"Walsh", "Mendez", "Nguyen"} <= names(result["eligible_doctors"])
    assert "Chen" in names(result["rejected_doctors"])
    assert "Brooks" in names(result["rejected_doctors"])
    assert "Torres" in names(result["rejected_doctors"])
    ranked_names = [item["doctor"]["last_name"] for item in result["ranked_recommendations"]]
    assert ranked_names == ["Walsh", "Mendez", "Nguyen"]
    assert result["ranked_recommendations"][-1]["primary_specialty"] == "General Orthopedics"
    assert all(
        not any(capability["body_part"] == "Foot/Ankle" for capability in item["doctor"]["capabilities"])
        for item in result["rejected_doctors"]
        if item["doctor"]["last_name"] in {"Chen", "Brooks", "Torres"}
    )


def test_alternative_location_is_searched_when_preferred_location_has_no_slots(
    client: FlaskClient,
    ids: dict[str, dict[str, int]],
) -> None:
    first_weekday = _first_future_weekday()
    starts_after, ends_before = _local_day_bounds(first_weekday)
    db_session = get_session_factory()()
    try:
        main_slots = db_session.scalars(
            select(Slot)
            .join(Doctor, Slot.doctor_id == Doctor.id)
            .where(
                Doctor.last_name.in_(["Chen", "Vasquez"]),
                Slot.location_id == ids["locations"]["MAIN"],
                Slot.starts_at >= starts_after,
                Slot.starts_at < ends_before,
            )
        ).all()
        assert main_slots
        for slot in main_slots:
            if db_session.scalar(select(Appointment.id).where(Appointment.slot_id == slot.id)) is None:
                slot.status = "BOOKED"
        db_session.commit()
    finally:
        db_session.close()

    result = route(
        client,
        body_part="Knee",
        issue_type="Sports Medicine",
        preferred_location_id=ids["locations"]["MAIN"],
        starts_after=starts_after.isoformat(),
        ends_before=ends_before.isoformat(),
    )

    assert result["recommended"]["available_slots"][0]["location"]["code"] in {"NORTH", "WEST"}
    assert result["recommended"]["preferred_location_match"] is False
    assert result["location_fallback"]["reason_code"] == "PREFERRED_LOCATION_UNAVAILABLE"


def test_no_match_summary_is_patient_safe(client: FlaskClient) -> None:
    result = route(client, body_part="Spine", issue_type="Fracture")

    assert result["recommended"] is None
    assert result["caller_safe_summary"] == (
        "We couldn't safely schedule this request online. Our care team will review it and follow up with you."
    )


def test_top_three_reserves_general_orthopedics_when_multiple_specialists_are_available(
    client: FlaskClient,
) -> None:
    result = route(client, body_part="Knee", issue_type="Sports Medicine")

    ranked_names = [item["doctor"]["last_name"] for item in result["ranked_recommendations"]]
    assert len(ranked_names) == 3
    assert ranked_names[-1] == "Nguyen"
    assert [item["is_general_orthopedics"] for item in result["ranked_recommendations"]].count(True) == 1
    assert all(not item["is_general_orthopedics"] for item in result["ranked_recommendations"][:2])


def test_routing_audit_records_location_redirect_context(client: FlaskClient, ids: dict[str, dict[str, int]]) -> None:
    call = client.post(
        "/api/v1/calls",
        json={
            "caller_phone": "+18055551234",
            "patient_status": "NEW",
            "requested_body_part": "Foot/Ankle",
            "requested_issue_type": "General",
            "preferred_location_id": ids["locations"]["MAIN"],
        },
    ).get_json()["call"]
    result = route(
        client,
        body_part="Foot/Ankle",
        issue_type="General",
        preferred_location_id=ids["locations"]["MAIN"],
        call_id=call["id"],
    )
    assert result["recommended"]["doctor"]["last_name"] == "Walsh"

    login = client.post("/api/auth/admin/login", json={"email": "admin@example.com", "password": "admin123"})
    assert login.status_code == 200
    audit = client.get("/api/v1/routing-audit")
    assert audit.status_code == 200
    decision = next(
        item
        for item in audit.get_json()["decisions"]
        if item["call_id"] == call["id"] and item["reason_code"] == "FALLBACK_SELECTED"
    )

    context = decision["request_context"]
    assert context["preferred_location"]["code"] == "MAIN"
    assert context["selected_alternative_location"]["code"] == "NORTH"
    assert context["redirect_reason"] == "PREFERRED_LOCATION_UNAVAILABLE"
    assert [item["doctor_name"] for item in context["ranked_recommendations"]] == [
        "Dr. James Walsh",
        "Dr. Carlos Mendez",
        "Dr. David Nguyen",
    ]
    assert [item["code"] for item in context["locations_searched"]] == ["MAIN", "EAST", "NORTH", "WEST", "SOUTH"]


def test_exactly_one_general_orthopedics_physician(client: FlaskClient) -> None:
    protocol = client.get("/api/v1/protocol").get_json()
    general = [doctor for doctor in protocol["doctors"] if doctor["is_general_orthopedics"]]

    assert [(doctor["first_name"], doctor["last_name"]) for doctor in general] == [("David", "Nguyen")]
    assert general[0]["primary_specialty"] == "General Orthopedics"
    assert general[0]["accepts_new_patients"] is True


def test_general_orthopedics_seed_rotation_uses_all_five_clinics(client: FlaskClient) -> None:
    db_session = get_session_factory()()
    clinic_tz = ZoneInfo("America/Los_Angeles")
    expected_by_weekday = {
        0: "MAIN",
        1: "EAST",
        2: "NORTH",
        3: "WEST",
        4: "SOUTH",
    }
    try:
        nguyen = db_session.scalar(select(Doctor).where(Doctor.first_name == "David", Doctor.last_name == "Nguyen"))
        assert nguyen is not None
        slots = db_session.scalars(
            select(Slot)
            .where(Slot.doctor_id == nguyen.id, Slot.status == "OPEN", Slot.starts_at >= datetime.now(UTC))
            .order_by(Slot.starts_at)
        ).all()

        local_starts = [
            (slot.starts_at if slot.starts_at.tzinfo else slot.starts_at.replace(tzinfo=UTC)).astimezone(clinic_tz)
            for slot in slots
        ]
        future_weeks = {local_start.isocalendar().week for local_start in local_starts}
        assert len(future_weeks) >= 4
        assert {local_start.hour < 12 for local_start in local_starts} == {False, True}
        for slot, local_start in zip(slots, local_starts, strict=True):
            if local_start.weekday() >= 5:
                continue
            assert slot.location.code == expected_by_weekday[local_start.weekday()]
    finally:
        db_session.close()


@pytest.mark.parametrize(
    "body_part",
    ["Shoulder", "Upper Arm", "Elbow", "Forearm", "Hand/Wrist", "Hip", "Upper Leg", "Knee", "Lower Leg", "Foot/Ankle"],
)
def test_general_orthopedics_reaches_supported_common_body_parts(client: FlaskClient, body_part: str) -> None:
    result = route(client, body_part=body_part, issue_type="General")

    assert any(item["doctor"]["last_name"] == "Nguyen" for item in result["ranked_recommendations"])


def test_jordan_returning_right_knee_north_follow_up_reaches_walsh_slot(
    client: FlaskClient, ids: dict[str, dict[str, int]]
) -> None:
    lookup = client.post(
        "/api/v1/patients/lookup",
        json={"phone": "805-264-4217", "date_of_birth": "1988-09-22"},
    ).get_json()
    result = route(
        client,
        patient_id=lookup["patient"]["id"],
        patient_status="RETURNING",
        body_part="Knee",
        issue_type="Sports Medicine",
        preferred_location_id=ids["locations"]["NORTH"],
    )
    assert result["recommended"]["doctor"]["last_name"] == "Walsh"
    first_slot = result["recommended"]["available_slots"][0]
    assert first_slot["location"]["code"] == "NORTH"
    assert first_slot["display_time"].endswith("AM")


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


def _first_future_weekday() -> date:
    today = datetime.now(UTC).astimezone(ZoneInfo("America/Los_Angeles")).date()
    for day_offset in range(1, 15):
        day = today + timedelta(days=day_offset)
        if day.weekday() < 5:
            return day
    return today + timedelta(days=1)


def _local_day_bounds(day: date) -> tuple[datetime, datetime]:
    clinic_tz = ZoneInfo("America/Los_Angeles")
    starts_at = datetime.combine(day, time.min, tzinfo=clinic_tz).astimezone(UTC)
    ends_at = datetime.combine(day + timedelta(days=1), time.min, tzinfo=clinic_tz).astimezone(UTC)
    return starts_at, ends_at
