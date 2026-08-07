from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from flask import Flask
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.business_hours import is_within_business_hours
from app.domain.routing import PhysicianRoutingService, RoutingRequest
from app.errors import ApiError
from app.extensions import get_session_factory
from app.models import BookingConfirmation, Organization, Slot
from app.services.booking import BookingService


def test_is_within_business_hours_logic() -> None:
    tz = ZoneInfo("America/Los_Angeles")
    start = datetime(2026, 8, 3, 9, 0, tzinfo=tz).astimezone(UTC)
    end = start + timedelta(minutes=45)

    bh = {"Monday": "9:00 AM - 5:00 PM"}

    # Valid
    assert is_within_business_hours(start, end, bh, "America/Los_Angeles") is True

    # Early (Invalid)
    early_start = datetime(2026, 8, 3, 8, 0, tzinfo=tz).astimezone(UTC)
    early_end = early_start + timedelta(minutes=45)
    assert is_within_business_hours(early_start, early_end, bh, "America/Los_Angeles") is False

    # Late (Invalid)
    late_start = datetime(2026, 8, 3, 16, 30, tzinfo=tz).astimezone(UTC)
    late_end = late_start + timedelta(minutes=45)
    assert is_within_business_hours(late_start, late_end, bh, "America/Los_Angeles") is False

    # Empty (Valid - preserves legacy behavior)
    assert is_within_business_hours(start, end, {}, "America/Los_Angeles") is True


def test_routing_respects_business_hours(app: Flask) -> None:
    with app.app_context():
        session = get_session_factory()()
        org = session.scalar(select(Organization).where(Organization.slug == "default-orthopedics"))
        assert org is not None

        # Restrict business hours to Sunday only (no slots should normally exist then, or we can test exclusion)
        org.business_hours = {"Sunday": "9:00 AM - 10:00 AM"}
        session.commit()

        routing = PhysicianRoutingService(session)
        starts_after = datetime.now(UTC)
        ends_before = starts_after + timedelta(days=7)
        slots = routing._open_slots(org.id, starts_after, ends_before)

        # Because all seeded slots are typically M-F, slots should be empty now
        assert len(slots) == 0

        # Allow all days
        org.business_hours = {
            "Monday": "8:00 AM - 6:00 PM",
            "Tuesday": "8:00 AM - 6:00 PM",
            "Wednesday": "8:00 AM - 6:00 PM",
            "Thursday": "8:00 AM - 6:00 PM",
            "Friday": "8:00 AM - 6:00 PM",
        }
        session.commit()

        slots_restored = routing._open_slots(org.id, starts_after, ends_before)
        assert len(slots_restored) > 0


def test_booking_respects_business_hours(app: Flask) -> None:
    with app.app_context():
        session = get_session_factory()()
        org = session.scalar(select(Organization).where(Organization.slug == "default-orthopedics"))
        assert org is not None

        slot = session.scalar(select(Slot).where(Slot.organization_id == org.id, Slot.status == "OPEN"))
        assert slot is not None

        # Ensure slot is within some normal business hours to start with
        org.business_hours = {}
        session.commit()

        # We should be able to book this slot if it had a confirmation token.
        # To test business hours explicitly raising an error, we set impossible business hours.
        org.business_hours = {"Sunday": "1:00 AM - 2:00 AM"}

        # Create a valid confirmation token
        confirmation = BookingConfirmation(
            confirmation_token="dummy_token_123",
            patient_id=1,
            slot_id=slot.id,
            doctor_id=slot.doctor_id,
            location_id=slot.location_id,
            body_part="Knee",
            issue_type="General",
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            confirmed_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            status="CONFIRMED",
        )
        session.add(confirmation)
        session.commit()

        booking_service = BookingService(session)
        with pytest.raises(ApiError) as exc_info:
            # Patient ID 1, slot ID slot.id
            booking_service.book(
                patient_id=1,
                slot_id=slot.id,
                body_part="Knee",
                issue_type="General",
                call_id=None,
                booking_source="TEST",
                confirmation_token="dummy_token_123",
            )

        assert exc_info.value.code == "PHYSICIAN_NOT_ELIGIBLE"
