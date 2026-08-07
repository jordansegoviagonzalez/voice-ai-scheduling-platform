from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.domain.routing import PhysicianRoutingService, RoutingRequest
from app.extensions import get_session_factory
from app.models import Doctor, DoctorCapability, Location, Organization, Slot


def test_cross_specialty_routing_uses_selected_organization_only(client) -> None:  # type: ignore[no-untyped-def]
    session = get_session_factory()()
    try:
        cardiology_org, cardiology_doctor = _doctor_with_slot(
            session,
            slug="lakeside-cardiology-routing",
            organization_name="Lakeside Cardiology Routing",
            doctor_first_name="Cara",
            doctor_last_name="Pulse",
            area="Heart/Circulation",
            issue_type="Routine Consult",
        )
        _dental_org, dental_doctor = _doctor_with_slot(
            session,
            slug="northside-dental-routing",
            organization_name="Northside Dental Routing",
            doctor_first_name="Dina",
            doctor_last_name="Mouth",
            area="Mouth/Teeth/Tongue",
            issue_type="Pain",
        )
        session.flush()

        result = PhysicianRoutingService(session).recommend(
            RoutingRequest(
                organization_id=cardiology_org.id,
                patient_id=None,
                patient_status="NEW",
                body_part="Heart/Circulation",
                issue_type="Routine Consult",
                starts_after=datetime.now(UTC),
                ends_before=datetime.now(UTC) + timedelta(days=2),
            ),
            persist=False,
        )

        assert result["recommended"]["doctor"]["id"] == cardiology_doctor.id
        eligible_ids = {item["doctor"]["id"] for item in result["eligible_doctors"]}
        assert cardiology_doctor.id in eligible_ids
        assert dental_doctor.id not in eligible_ids
    finally:
        session.close()


def test_cross_specialty_routing_returns_no_match_for_unavailable_capability(client) -> None:  # type: ignore[no-untyped-def]
    session = get_session_factory()()
    try:
        organization, _doctor = _doctor_with_slot(
            session,
            slug="primary-care-no-match",
            organization_name="Primary Care No Match",
            doctor_first_name="Priya",
            doctor_last_name="General",
            area="Primary Care",
            issue_type="Routine Consult",
        )
        session.flush()

        result = PhysicianRoutingService(session).recommend(
            RoutingRequest(
                organization_id=organization.id,
                patient_id=None,
                patient_status="NEW",
                body_part="Mouth/Teeth/Tongue",
                issue_type="Pain",
                starts_after=datetime.now(UTC),
                ends_before=datetime.now(UTC) + timedelta(days=2),
            ),
            persist=False,
        )

        assert result["recommended"] is None
        assert result["ranked_recommendations"] == []
        assert result["rejected_doctors"][0]["reason_code"] == "BODY_PART_NOT_SUPPORTED"
    finally:
        session.close()


def _doctor_with_slot(
    session: Session,
    *,
    slug: str,
    organization_name: str,
    doctor_first_name: str,
    doctor_last_name: str,
    area: str,
    issue_type: str,
) -> tuple[Organization, Doctor]:
    organization = Organization(slug=slug, name=organization_name, status="ACTIVE", timezone="America/Los_Angeles")
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
    return organization, doctor
