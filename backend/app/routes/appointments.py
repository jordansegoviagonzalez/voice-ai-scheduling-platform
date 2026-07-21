from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.errors import ApiError
from app.extensions import get_session
from app.models import Appointment, Doctor
from app.routes.common import bounded_string, int_or_none, json_body, require_fields
from app.services.booking import BookingService
from app.services.serializers import appointment_json

bp = Blueprint("appointments", __name__)


def _appointment_query():  # type: ignore[no-untyped-def]
    return select(Appointment).options(
        selectinload(Appointment.patient),
        selectinload(Appointment.doctor).selectinload(Doctor.locations),
        selectinload(Appointment.doctor).selectinload(Doctor.capabilities),
        selectinload(Appointment.location),
        selectinload(Appointment.slot),
    )


@bp.post("/appointments")
def create_appointment():  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(payload, "patient_id", "slot_id", "body_part", "issue_type", "confirmation_token")
    session = get_session()
    appointment = BookingService(session).book(
        patient_id=int(payload["patient_id"]),
        slot_id=int(payload["slot_id"]),
        body_part=bounded_string(payload, "body_part", max_length=32) or "",
        issue_type=bounded_string(payload, "issue_type", max_length=32) or "",
        call_id=int_or_none(payload.get("call_id"), "call_id"),
        booking_source=bounded_string(payload, "booking_source", max_length=32, required=False) or "WEB",
        confirmation_token=bounded_string(payload, "confirmation_token", max_length=128) or "",
    )
    appointment = session.scalar(_appointment_query().where(Appointment.id == appointment.id))
    assert appointment is not None
    return jsonify({"appointment": appointment_json(appointment)}), 201


@bp.get("/appointments")
def list_appointments():  # type: ignore[no-untyped-def]
    appointments = list(get_session().scalars(_appointment_query().order_by(Appointment.created_at.desc())))
    return jsonify({"appointments": [appointment_json(item) for item in appointments]})


@bp.get("/appointments/<int:appointment_id>")
def get_appointment(appointment_id: int):  # type: ignore[no-untyped-def]
    appointment = get_session().scalar(_appointment_query().where(Appointment.id == appointment_id))
    if appointment is None:
        raise ApiError("APPOINTMENT_NOT_FOUND", "Appointment was not found.", 404)
    return jsonify({"appointment": appointment_json(appointment)})
