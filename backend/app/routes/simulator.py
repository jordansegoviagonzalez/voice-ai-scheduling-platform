from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.normalization import normalize_phone
from app.domain.routing import PhysicianRoutingService, RoutingRequest
from app.extensions import get_session
from app.models import Appointment, Call, Doctor, Patient, RoutingDecision, TranscriptTurn
from app.routes.common import bounded_string, int_or_none, json_body, parse_date, require_fields
from app.services.booking import BookingService
from app.services.confirmation import BookingConfirmationService
from app.services.serializers import appointment_json, call_json, patient_json

bp = Blueprint("simulator", __name__)


def _append_turn(call: Call, speaker: str, text: str, sequence: int) -> None:
    now = datetime.now(UTC)
    call.transcript_turns.append(
        TranscriptTurn(
            sequence_number=sequence,
            speaker=speaker,
            text=text,
            occurred_at=now,
        )
    )
    call.transcript = [
        *call.transcript,
        {
            "sequence_number": sequence,
            "speaker": speaker,
            "text": text,
            "occurred_at": now.isoformat(),
        },
    ]


@bp.post("/simulator/preview")
def simulator_preview():  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(
        payload,
        "caller_phone",
        "first_name",
        "last_name",
        "date_of_birth",
        "patient_status",
        "body_part",
        "issue_type",
    )
    session = get_session()
    phone = normalize_phone(bounded_string(payload, "caller_phone", max_length=32) or "")
    first_name = bounded_string(payload, "first_name", max_length=100) or ""
    last_name = bounded_string(payload, "last_name", max_length=100) or ""
    dob = parse_date(bounded_string(payload, "date_of_birth", max_length=10) or "", "date_of_birth")
    patient_status = bounded_string(payload, "patient_status", max_length=16) or ""
    body_part = bounded_string(payload, "body_part", max_length=32) or ""
    issue_type = bounded_string(payload, "issue_type", max_length=32) or ""
    patient = session.scalar(select(Patient).where(Patient.phone == phone, Patient.date_of_birth == dob))
    if patient is None:
        patient = Patient(
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            phone=phone,
            email=None,
        )
        session.add(patient)
        session.flush()

    call = Call(
        patient_id=patient.id,
        status="IN_PROGRESS",
        caller_phone=phone,
        patient_status=patient_status.upper(),
        requested_body_part=body_part,
        requested_issue_type=issue_type,
        preferred_doctor_id=int_or_none(payload.get("preferred_doctor_id"), "preferred_doctor_id"),
        preferred_location_id=int_or_none(payload.get("preferred_location_id"), "preferred_location_id"),
        started_at=datetime.now(UTC),
        transcript=[],
    )
    session.add(call)
    session.flush()
    _append_turn(call, "AI", "Thank you for calling. I can help schedule an orthopedic appointment.", 1)
    _append_turn(call, "HUMAN", f"My name is {patient.full_name}.", 2)
    _append_turn(
        call,
        "HUMAN",
        f"I need an appointment for {body_part} - {issue_type}.",
        3,
    )

    routing = PhysicianRoutingService(session).recommend(
        RoutingRequest(
            patient_id=patient.id,
            patient_status=patient_status,
            body_part=body_part,
            issue_type=issue_type,
            preferred_doctor_id=call.preferred_doctor_id,
            preferred_location_id=call.preferred_location_id,
            call_id=call.id,
        )
    )
    _append_turn(call, "AI", routing["caller_safe_summary"], 4)
    if routing["recommended"] is None:
        call.status = "REDIRECTED"
        call.redirect_summary = routing["caller_safe_summary"]
        call.ended_at = datetime.now(UTC)
    session.commit()
    hydrated = session.scalar(
        select(Call)
        .where(Call.id == call.id)
        .options(
            selectinload(Call.patient),
            selectinload(Call.preferred_doctor).selectinload(Doctor.locations),
            selectinload(Call.preferred_doctor).selectinload(Doctor.capabilities),
            selectinload(Call.preferred_location),
            selectinload(Call.transcript_turns),
            selectinload(Call.routing_decisions).selectinload(RoutingDecision.doctor),
        )
    )
    assert hydrated is not None
    return jsonify(
        {
            "patient": patient_json(patient),
            "call": call_json(hydrated, detailed=True),
            "routing": routing,
        }
    ), 201


@bp.post("/simulator/book")
def simulator_book():  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(payload, "call_id", "patient_id", "slot_id", "body_part", "issue_type", "confirmation_token")
    session = get_session()
    appointment = BookingService(session).book(
        patient_id=int(payload["patient_id"]),
        slot_id=int(payload["slot_id"]),
        body_part=bounded_string(payload, "body_part", max_length=32) or "",
        issue_type=bounded_string(payload, "issue_type", max_length=32) or "",
        call_id=int(payload["call_id"]),
        booking_source="SIMULATOR",
        confirmation_token=bounded_string(payload, "confirmation_token", max_length=128) or "",
    )
    call = session.get(Call, int(payload["call_id"]))
    assert call is not None
    slot = appointment.slot
    _append_turn(
        call,
        "HUMAN",
        "Yes, please book that doctor, location, date, and time.",
        len(call.transcript) + 1,
    )
    _append_turn(
        call,
        "AI",
        (
            f"Your appointment is confirmed with {appointment.doctor.full_name} at "
            f"{appointment.location.name} on {slot.starts_at.isoformat()}."
        ),
        len(call.transcript) + 1,
    )
    session.commit()
    hydrated_appointment = session.scalar(
        select(Appointment)
        .where(Appointment.id == appointment.id)
        .options(
            selectinload(Appointment.patient),
            selectinload(Appointment.doctor).selectinload(Doctor.locations),
            selectinload(Appointment.doctor).selectinload(Doctor.capabilities),
            selectinload(Appointment.location),
            selectinload(Appointment.slot),
        )
    )
    assert hydrated_appointment is not None
    return jsonify({"appointment": appointment_json(hydrated_appointment)}), 201


@bp.post("/simulator/confirm")
def simulator_confirm():  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(payload, "call_id", "patient_id", "slot_id", "body_part", "issue_type")
    confirmation = BookingConfirmationService(get_session()).confirm(
        call_id=int(payload["call_id"]),
        patient_id=int(payload["patient_id"]),
        slot_id=int(payload["slot_id"]),
        body_part=bounded_string(payload, "body_part", max_length=32) or "",
        issue_type=bounded_string(payload, "issue_type", max_length=32) or "",
        source="SIMULATOR",
    )
    return jsonify({"confirmation_token": confirmation.confirmation_token}), 201
