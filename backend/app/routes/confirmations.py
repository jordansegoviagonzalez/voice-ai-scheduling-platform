from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions import get_session
from app.models import BookingConfirmation, Doctor
from app.routes.common import bounded_string, json_body, require_fields
from app.services.confirmation import BookingConfirmationService
from app.services.serializers import booking_confirmation_json

bp = Blueprint("confirmations", __name__)


def _confirmation_query():  # type: ignore[no-untyped-def]
    return select(BookingConfirmation).options(
        selectinload(BookingConfirmation.doctor).selectinload(Doctor.locations),
        selectinload(BookingConfirmation.doctor).selectinload(Doctor.capabilities),
        selectinload(BookingConfirmation.location),
        selectinload(BookingConfirmation.slot),
    )


@bp.post("/booking-confirmations")
def create_booking_confirmation():  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(payload, "call_id", "patient_id", "slot_id", "body_part", "issue_type")
    session = get_session()
    confirmation = BookingConfirmationService(session).confirm(
        call_id=int(payload["call_id"]),
        patient_id=int(payload["patient_id"]),
        slot_id=int(payload["slot_id"]),
        body_part=bounded_string(payload, "body_part", max_length=32) or "",
        issue_type=bounded_string(payload, "issue_type", max_length=32) or "",
        source=bounded_string(payload, "source", max_length=32, required=False) or "API",
    )
    hydrated = session.scalar(_confirmation_query().where(BookingConfirmation.id == confirmation.id))
    assert hydrated is not None
    return jsonify({"confirmation": booking_confirmation_json(hydrated)}), 201
