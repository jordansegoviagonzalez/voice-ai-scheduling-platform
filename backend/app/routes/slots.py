from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.normalization import normalize_body_part, normalize_issue_type
from app.extensions import get_session
from app.models import Doctor, DoctorCapability, Slot
from app.routes.common import int_or_none, parse_datetime
from app.services.serializers import slot_json

bp = Blueprint("slots", __name__)


@bp.get("/slots")
def list_slots():  # type: ignore[no-untyped-def]
    doctor_id = int_or_none(request.args.get("doctor_id"), "doctor_id")
    location_id = int_or_none(request.args.get("location_id"), "location_id")
    body_part = request.args.get("body_part")
    issue_type = request.args.get("issue_type")
    starts_after = parse_datetime(request.args.get("starts_after"), "starts_after") or datetime.now(UTC)
    ends_before = parse_datetime(request.args.get("ends_before"), "ends_before") or starts_after + timedelta(days=14)

    statement = (
        select(Slot)
        .where(Slot.status == "OPEN", Slot.starts_at >= starts_after, Slot.starts_at < ends_before)
        .options(
            selectinload(Slot.doctor).selectinload(Doctor.locations),
            selectinload(Slot.doctor).selectinload(Doctor.capabilities),
            selectinload(Slot.location),
        )
        .order_by(Slot.starts_at, Slot.id)
    )
    if doctor_id:
        statement = statement.where(Slot.doctor_id == doctor_id)
    if location_id:
        statement = statement.where(Slot.location_id == location_id)
    if body_part or issue_type:
        canonical_body = normalize_body_part(body_part or "")
        canonical_issue = normalize_issue_type(issue_type or "")
        statement = statement.join(DoctorCapability, DoctorCapability.doctor_id == Slot.doctor_id).where(
            DoctorCapability.body_part == canonical_body,
            DoctorCapability.issue_type == canonical_issue,
        )
    slots = list(get_session().scalars(statement).unique())
    return jsonify({"slots": [slot_json(item) for item in slots]})
