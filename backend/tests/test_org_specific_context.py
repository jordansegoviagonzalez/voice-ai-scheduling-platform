from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask.testing import FlaskClient

from app.extensions import get_session_factory
from app.models import Call, ChatSession, Doctor, DoctorCapability, Location, Organization, Slot


def test_org_slug_chat_session_persists_and_enforces_organization_context(client: FlaskClient) -> None:
    org_a, _doctor_a = _doctor_with_slot(
        slug="lakeside-chat-context",
        organization_name="Lakeside Chat Context",
        doctor_first_name="Cara",
        doctor_last_name="Pulse",
        area="Heart/Circulation",
        issue_type="Routine Consult",
    )
    org_b, _doctor_b = _doctor_with_slot(
        slug="northside-chat-context",
        organization_name="Northside Chat Context",
        doctor_first_name="Dina",
        doctor_last_name="Mouth",
        area="Mouth/Teeth/Tongue",
        issue_type="Pain",
    )

    created = client.post(
        f"/api/chat/organizations/{org_a.slug}/sessions",
        json={
            "patientMode": "returning",
            "email": "olivia.carter.phase2.demo@example.com",
            "password": "Patient!2026",
        },
    )

    assert created.status_code == 201, created.get_json()
    session_id = created.get_json()["sessionId"]
    db_session = get_session_factory()()
    try:
        chat_session = db_session.get(ChatSession, session_id)
        assert chat_session is not None
        assert chat_session.organization_id == org_a.id
    finally:
        db_session.close()

    restored = client.get(f"/api/chat/organizations/{org_a.slug}/sessions/{session_id}")
    assert restored.status_code == 200, restored.get_json()

    wrong_org = client.get(f"/api/chat/organizations/{org_b.slug}/sessions/{session_id}")
    assert wrong_org.status_code == 404, wrong_org.get_json()
    assert wrong_org.get_json()["error"]["code"] == "CHAT_SESSION_NOT_FOUND"


def test_org_slug_chat_session_rejects_unknown_and_inactive_organizations(client: FlaskClient) -> None:
    inactive_org, _doctor = _doctor_with_slot(
        slug="inactive-chat-context",
        organization_name="Inactive Chat Context",
        doctor_first_name="Ivy",
        doctor_last_name="Paused",
        area="Primary Care",
        issue_type="Routine Consult",
        status="INACTIVE",
    )

    unknown = client.post(
        "/api/chat/organizations/not-a-real-org/sessions",
        json={
            "patientMode": "returning",
            "email": "olivia.carter.phase2.demo@example.com",
            "password": "Patient!2026",
        },
    )
    inactive = client.post(
        f"/api/chat/organizations/{inactive_org.slug}/sessions",
        json={
            "patientMode": "returning",
            "email": "olivia.carter.phase2.demo@example.com",
            "password": "Patient!2026",
        },
    )

    assert unknown.status_code == 404, unknown.get_json()
    assert unknown.get_json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"
    assert inactive.status_code == 409, inactive.get_json()
    assert inactive.get_json()["error"]["code"] == "ORGANIZATION_INACTIVE"


def test_org_slug_protocol_and_routing_use_only_selected_organization(client: FlaskClient) -> None:
    cardiology_org, cardiology_doctor = _doctor_with_slot(
        slug="lakeside-cardiology-context",
        organization_name="Lakeside Cardiology Context",
        doctor_first_name="Cara",
        doctor_last_name="Pulse",
        area="Heart/Circulation",
        issue_type="Routine Consult",
    )
    _dental_org, dental_doctor = _doctor_with_slot(
        slug="northside-dental-context",
        organization_name="Northside Dental Context",
        doctor_first_name="Dina",
        doctor_last_name="Mouth",
        area="Mouth/Teeth/Tongue",
        issue_type="Pain",
    )

    protocol = client.get(f"/api/v1/organizations/slug/{cardiology_org.slug}/protocol")
    assert protocol.status_code == 200, protocol.get_json()
    protocol_doctor_ids = {doctor["id"] for doctor in protocol.get_json()["doctors"]}
    assert cardiology_doctor.id in protocol_doctor_ids
    assert dental_doctor.id not in protocol_doctor_ids

    routing = client.post(
        f"/api/v1/organizations/slug/{cardiology_org.slug}/routing/recommendations",
        json={
            "patient_status": "NEW",
            "body_part": "Heart/Circulation",
            "issue_type": "Routine Consult",
        },
    )

    assert routing.status_code == 200, routing.get_json()
    payload = routing.get_json()
    assert payload["recommended"]["doctor"]["id"] == cardiology_doctor.id
    eligible_ids = {doctor["doctor"]["id"] for doctor in payload["eligible_doctors"]}
    assert cardiology_doctor.id in eligible_ids
    assert dental_doctor.id not in eligible_ids


def test_org_slug_routing_no_match_does_not_fall_back_to_another_organization(client: FlaskClient) -> None:
    cardiology_org, cardiology_doctor = _doctor_with_slot(
        slug="lakeside-no-dental-context",
        organization_name="Lakeside No Dental Context",
        doctor_first_name="Cara",
        doctor_last_name="Pulse",
        area="Heart/Circulation",
        issue_type="Routine Consult",
    )
    _dental_org, dental_doctor = _doctor_with_slot(
        slug="northside-no-leak-context",
        organization_name="Northside No Leak Context",
        doctor_first_name="Dina",
        doctor_last_name="Mouth",
        area="Mouth/Teeth/Tongue",
        issue_type="Pain",
    )

    response = client.post(
        f"/api/v1/organizations/slug/{cardiology_org.slug}/routing/recommendations",
        json={
            "patient_status": "NEW",
            "body_part": "Mouth/Teeth/Tongue",
            "issue_type": "Pain",
        },
    )

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["recommended"] is None
    assert payload["ranked_recommendations"] == []
    eligible_ids = {doctor["doctor"]["id"] for doctor in payload["eligible_doctors"]}
    rejected_ids = {doctor["doctor"]["id"] for doctor in payload["rejected_doctors"]}
    assert dental_doctor.id not in eligible_ids
    assert dental_doctor.id not in rejected_ids
    assert cardiology_doctor.id in rejected_ids


def test_org_slug_routing_rejects_invalid_organization(client: FlaskClient) -> None:
    response = client.post(
        "/api/v1/organizations/slug/not-a-real-org/routing/recommendations",
        json={
            "patient_status": "NEW",
            "body_part": "Heart/Circulation",
            "issue_type": "Routine Consult",
        },
    )

    assert response.status_code == 404, response.get_json()
    assert response.get_json()["error"]["code"] == "ORGANIZATION_NOT_FOUND"


def test_org_slug_vogent_inbound_and_routing_use_selected_organization(client: FlaskClient) -> None:
    cardiology_org, cardiology_doctor = _doctor_with_slot(
        slug="lakeside-vogent-context",
        organization_name="Lakeside Vogent Context",
        doctor_first_name="Cara",
        doctor_last_name="Pulse",
        area="Heart/Circulation",
        issue_type="Routine Consult",
    )
    dental_org, dental_doctor = _doctor_with_slot(
        slug="northside-vogent-context",
        organization_name="Northside Vogent Context",
        doctor_first_name="Dina",
        doctor_last_name="Mouth",
        area="Mouth/Teeth/Tongue",
        issue_type="Pain",
    )

    inbound = client.post(
        f"/api/v1/organizations/slug/{cardiology_org.slug}/vogent/webhooks",
        json={
            "event": "dial.inbound",
            "event_id": "org-context-inbound",
            "payload": {"dial_id": "dial-org-context-001", "source_number": "+18055556001"},
        },
    )

    assert inbound.status_code == 200, inbound.get_json()
    call_id = int(inbound.get_json()["call_agent_input"]["internal_call_id"])
    db_session = get_session_factory()()
    try:
        call = db_session.get(Call, call_id)
        assert call is not None
        assert call.organization_id == cardiology_org.id
    finally:
        db_session.close()

    routing = client.post(
        f"/api/v1/organizations/slug/{cardiology_org.slug}/vogent/functions/routing-recommendations",
        json={
            "call_id": call_id,
            "patient_status": "NEW",
            "body_part": "Heart/Circulation",
            "issue_type": "Routine Consult",
        },
    )
    assert routing.status_code == 200, routing.get_json()
    assert routing.get_json()["recommended_doctor_id"] == cardiology_doctor.id
    assert routing.get_json()["recommended_doctor_id"] != dental_doctor.id

    wrong_org = client.post(
        f"/api/v1/organizations/slug/{dental_org.slug}/vogent/functions/routing-recommendations",
        json={
            "call_id": call_id,
            "patient_status": "NEW",
            "body_part": "Mouth/Teeth/Tongue",
            "issue_type": "Pain",
        },
    )
    assert wrong_org.status_code == 409, wrong_org.get_json()
    assert wrong_org.get_json()["error"]["code"] == "ORGANIZATION_CONTEXT_MISMATCH"


def _doctor_with_slot(
    *,
    slug: str,
    organization_name: str,
    doctor_first_name: str,
    doctor_last_name: str,
    area: str,
    issue_type: str,
    status: str = "ACTIVE",
) -> tuple[Organization, Doctor]:
    session = get_session_factory()()
    try:
        organization = Organization(
            slug=slug,
            name=organization_name,
            status=status,
            timezone="America/Los_Angeles",
        )
        session.add(organization)
        session.flush()
        location = Location(organization_id=organization.id, code="MAIN", name=f"{organization_name} Main")
        session.add(location)
        session.flush()
        doctor = Doctor(
            organization_id=organization.id,
            first_name=doctor_first_name,
            last_name=doctor_last_name,
            accepts_new_patients=True,
            active=True,
        )
        doctor.locations = [location]
        doctor.capabilities = [DoctorCapability(body_part=area, issue_type=issue_type)]
        session.add(doctor)
        session.flush()
        starts_at = datetime.now(UTC) + timedelta(hours=2)
        session.add(
            Slot(
                organization_id=organization.id,
                doctor_id=doctor.id,
                location_id=location.id,
                starts_at=starts_at,
                ends_at=starts_at + timedelta(minutes=45),
                status="OPEN",
            )
        )
        session.commit()
        session.refresh(organization)
        session.refresh(doctor)
        return organization, doctor
    finally:
        session.close()
