from __future__ import annotations

from flask.testing import FlaskClient
from sqlalchemy import func, select

from app.extensions import get_session_factory
from app.models import Appointment, Call, ChatSession, Doctor, Location, Organization, RoutingDecision, Slot
from app.services.organization_context import DEFAULT_ORGANIZATION_SLUG


def test_seed_creates_default_organization_and_backfills_core_records(client: FlaskClient) -> None:
    session = get_session_factory()()
    try:
        organization = session.scalar(select(Organization).where(Organization.slug == DEFAULT_ORGANIZATION_SLUG))
        assert organization is not None
        assert organization.status == "ACTIVE"

        for model in (Location, Doctor, Slot, Appointment, Call, RoutingDecision):
            total = session.scalar(select(func.count(model.id)))
            scoped = session.scalar(select(func.count(model.id)).where(model.organization_id == organization.id))
            assert total == scoped
    finally:
        session.close()


def test_default_organization_preserves_protocol_response(client: FlaskClient) -> None:
    payload = client.get("/api/v1/protocol").get_json()

    doctor_names = {doctor["full_name"] for doctor in payload["doctors"]}
    location_codes = {location["code"] for location in payload["locations"]}

    assert "Dr. Maria Chen" in doctor_names
    assert "Dr. Sarah O'Brien" in doctor_names
    assert {"MAIN", "NORTH", "WEST"}.issubset(location_codes)


def test_legacy_chat_session_is_created_under_default_organization(client: FlaskClient) -> None:
    response = client.post(
        "/api/chat/sessions",
        json={
            "patientMode": "new",
            "firstName": "Foundation",
            "lastName": "Patient",
            "dateOfBirth": "1992-02-03",
            "phone": "+18055558881",
            "email": "foundation.patient@example.test",
            "password": "correct horse battery staple",
            "confirmPassword": "correct horse battery staple",
            "insuranceProvider": "Demo Health",
        },
    )

    assert response.status_code == 201, response.get_json()
    session_id = response.get_json()["sessionId"]

    session = get_session_factory()()
    try:
        organization = session.scalar(select(Organization).where(Organization.slug == DEFAULT_ORGANIZATION_SLUG))
        chat_session = session.get(ChatSession, session_id)
        assert organization is not None
        assert chat_session is not None
        assert chat_session.organization_id == organization.id
    finally:
        session.close()


def test_legacy_routing_audit_uses_default_organization(client: FlaskClient) -> None:
    call = client.post("/api/v1/calls", json={"caller_phone": "+18055558882"}).get_json()["call"]
    response = client.post(
        "/api/v1/routing/recommendations",
        json={
            "call_id": call["id"],
            "patient_status": "NEW",
            "body_part": "Knee",
            "issue_type": "Fracture",
        },
    )

    assert response.status_code == 200, response.get_json()

    session = get_session_factory()()
    try:
        organization = session.scalar(select(Organization).where(Organization.slug == DEFAULT_ORGANIZATION_SLUG))
        decisions = session.scalars(select(RoutingDecision).where(RoutingDecision.call_id == call["id"])).all()
        assert organization is not None
        assert decisions
        assert {decision.organization_id for decision in decisions} == {organization.id}
    finally:
        session.close()
