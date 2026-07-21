from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.errors import ApiError
from app.extensions import get_session
from app.models import Appointment, Call, Doctor, RoutingDecision, TranscriptTurn
from app.routes.common import bounded_string, int_or_none, json_body, parse_datetime, require_fields
from app.services.serializers import call_json

bp = Blueprint("calls", __name__)


def _call_query(detailed: bool = False):  # type: ignore[no-untyped-def]
    options = [
        selectinload(Call.patient),
        selectinload(Call.preferred_doctor).selectinload(Doctor.locations),
        selectinload(Call.preferred_doctor).selectinload(Doctor.capabilities),
        selectinload(Call.preferred_location),
        selectinload(Call.appointment).selectinload(Appointment.patient),
        selectinload(Call.appointment).selectinload(Appointment.location),
        selectinload(Call.appointment).selectinload(Appointment.slot),
        selectinload(Call.appointment).selectinload(Appointment.doctor).selectinload(Doctor.locations),
        selectinload(Call.appointment).selectinload(Appointment.doctor).selectinload(Doctor.capabilities),
    ]
    if detailed:
        options.extend(
            [
                selectinload(Call.transcript_turns),
                selectinload(Call.routing_decisions)
                .selectinload(RoutingDecision.doctor)
                .selectinload(Doctor.locations),
                selectinload(Call.routing_decisions)
                .selectinload(RoutingDecision.doctor)
                .selectinload(Doctor.capabilities),
            ]
        )
    return select(Call).options(*options)


@bp.post("/calls")
def create_call():  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(payload, "caller_phone")
    session = get_session()
    caller_phone = bounded_string(payload, "caller_phone", max_length=32) or ""
    call = Call(
        external_call_id=bounded_string(payload, "external_call_id", max_length=128, required=False),
        patient_id=int_or_none(payload.get("patient_id"), "patient_id"),
        status=str(payload.get("status", "IN_PROGRESS")).upper(),
        caller_phone=caller_phone,
        patient_status=str(payload["patient_status"]).upper() if payload.get("patient_status") else None,
        requested_body_part=bounded_string(payload, "requested_body_part", max_length=32, required=False),
        requested_issue_type=bounded_string(payload, "requested_issue_type", max_length=32, required=False),
        preferred_doctor_id=int_or_none(payload.get("preferred_doctor_id"), "preferred_doctor_id"),
        preferred_location_id=int_or_none(payload.get("preferred_location_id"), "preferred_location_id"),
        started_at=parse_datetime(payload.get("started_at"), "started_at") or datetime.now(UTC),
        ended_at=parse_datetime(payload.get("ended_at"), "ended_at"),
        transcript=[],
        failure_reason=bounded_string(payload, "failure_reason", max_length=1000, required=False),
        redirect_summary=bounded_string(payload, "redirect_summary", max_length=1000, required=False),
    )
    session.add(call)
    session.commit()
    hydrated = session.scalar(_call_query().where(Call.id == call.id))
    assert hydrated is not None
    return jsonify({"call": call_json(hydrated)}), 201


@bp.patch("/calls/<int:call_id>")
def update_call(call_id: int):  # type: ignore[no-untyped-def]
    payload = json_body(request)
    session = get_session()
    call = session.get(Call, call_id)
    if call is None:
        raise ApiError("CALL_NOT_FOUND", "Call was not found.", 404)
    if "status" in payload:
        call.status = str(payload["status"]).upper()
    if "patient_status" in payload:
        call.patient_status = str(payload["patient_status"]).upper() if payload["patient_status"] is not None else None
    for field in ("requested_body_part", "requested_issue_type", "failure_reason", "redirect_summary"):
        if field in payload:
            limit = 1000 if field in {"failure_reason", "redirect_summary"} else 32
            setattr(call, field, bounded_string(payload, field, max_length=limit, required=False))
    if "patient_id" in payload:
        call.patient_id = int_or_none(payload["patient_id"], "patient_id")
    if "preferred_doctor_id" in payload:
        call.preferred_doctor_id = int_or_none(payload["preferred_doctor_id"], "preferred_doctor_id")
    if "preferred_location_id" in payload:
        call.preferred_location_id = int_or_none(payload["preferred_location_id"], "preferred_location_id")
    if "ended_at" in payload:
        call.ended_at = parse_datetime(payload["ended_at"], "ended_at")
    session.commit()
    hydrated = session.scalar(_call_query(detailed=True).where(Call.id == call.id))
    assert hydrated is not None
    return jsonify({"call": call_json(hydrated, detailed=True)})


@bp.post("/calls/<int:call_id>/transcript-turns")
def add_transcript_turn(call_id: int):  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(payload, "speaker", "text")
    session = get_session()
    call = session.get(Call, call_id)
    if call is None:
        raise ApiError("CALL_NOT_FOUND", "Call was not found.", 404)
    latest_sequence = session.scalar(
        select(TranscriptTurn.sequence_number)
        .where(TranscriptTurn.call_id == call_id)
        .order_by(TranscriptTurn.sequence_number.desc())
        .limit(1)
    )
    turn = TranscriptTurn(
        call_id=call_id,
        sequence_number=int(payload.get("sequence_number", (latest_sequence or 0) + 1)),
        speaker=(bounded_string(payload, "speaker", max_length=16) or "").upper(),
        text=bounded_string(
            payload,
            "text",
            max_length=int(current_app.config.get("TRANSCRIPT_TURN_MAX_LENGTH", 2000)),
        )
        or "",
        occurred_at=parse_datetime(payload.get("occurred_at"), "occurred_at") or datetime.now(UTC),
    )
    session.add(turn)
    session.flush()
    call.transcript = [
        *call.transcript,
        {
            "sequence_number": turn.sequence_number,
            "speaker": turn.speaker,
            "text": turn.text,
            "occurred_at": turn.occurred_at.isoformat(),
        },
    ]
    session.commit()
    return (
        jsonify(
            {
                "transcript_turn": {
                    "id": turn.id,
                    "sequence_number": turn.sequence_number,
                    "speaker": turn.speaker,
                    "text": turn.text,
                    "occurred_at": turn.occurred_at.isoformat(),
                }
            }
        ),
        201,
    )


@bp.get("/calls")
def list_calls():  # type: ignore[no-untyped-def]
    status = request.args.get("status")
    doctor_id = int_or_none(request.args.get("doctor_id"), "doctor_id")
    location_id = int_or_none(request.args.get("location_id"), "location_id")
    search = request.args.get("search")
    starts_after = parse_datetime(request.args.get("starts_after"), "starts_after")
    ends_before = parse_datetime(request.args.get("ends_before"), "ends_before")

    statement = _call_query().order_by(Call.started_at.desc())
    if status:
        statement = statement.where(Call.status == status.upper())
    if doctor_id:
        statement = statement.outerjoin(Appointment, Call.appointment_id == Appointment.id).where(
            Appointment.doctor_id == doctor_id
        )
    if location_id:
        statement = statement.outerjoin(Appointment, Call.appointment_id == Appointment.id).where(
            Appointment.location_id == location_id
        )
    if starts_after:
        statement = statement.where(Call.started_at >= starts_after)
    if ends_before:
        statement = statement.where(Call.started_at < ends_before)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.outerjoin(Call.patient).where(
            or_(
                Call.caller_phone.ilike(pattern),
                Call.patient.has(first_name=search),
                Call.patient.has(last_name=search),
            )
        )
    calls = list(get_session().scalars(statement).unique())
    return jsonify({"calls": [call_json(item) for item in calls]})


@bp.get("/calls/<int:call_id>")
def get_call(call_id: int):  # type: ignore[no-untyped-def]
    call = get_session().scalar(_call_query(detailed=True).where(Call.id == call_id))
    if call is None:
        raise ApiError("CALL_NOT_FOUND", "Call was not found.", 404)
    return jsonify({"call": call_json(call, detailed=True)})
