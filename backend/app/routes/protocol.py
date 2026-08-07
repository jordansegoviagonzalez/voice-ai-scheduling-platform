from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.locations import location_sort_key
from app.domain.normalization import BODY_PARTS, ISSUE_TYPES
from app.errors import ApiError
from app.extensions import get_session
from app.models import Doctor, Location
from app.services.organization_context import default_organization_id
from app.services.serializers import doctor_json, location_json

bp = Blueprint("protocol", __name__)


def _doctor_query(organization_id: int):  # type: ignore[no-untyped-def]
    return (
        select(Doctor)
        .where(Doctor.organization_id == organization_id)
        .options(selectinload(Doctor.locations), selectinload(Doctor.capabilities))
        .order_by(Doctor.last_name, Doctor.first_name)
    )


@bp.get("/doctors")
def list_doctors():  # type: ignore[no-untyped-def]
    session = get_session()
    doctors = list(session.scalars(_doctor_query(default_organization_id(session))))
    return jsonify({"doctors": [doctor_json(item) for item in doctors]})


@bp.get("/doctors/<int:doctor_id>")
def get_doctor(doctor_id: int):  # type: ignore[no-untyped-def]
    session = get_session()
    doctor = session.scalar(_doctor_query(default_organization_id(session)).where(Doctor.id == doctor_id))
    if doctor is None:
        raise ApiError("DOCTOR_NOT_FOUND", "Physician was not found.", 404)
    return jsonify({"doctor": doctor_json(doctor)})


@bp.get("/locations")
def list_locations():  # type: ignore[no-untyped-def]
    session = get_session()
    organization_id = default_organization_id(session)
    locations = sorted(
        session.scalars(select(Location).where(Location.organization_id == organization_id)).all(),
        key=location_sort_key,
    )
    return jsonify({"locations": [location_json(item) for item in locations]})


@bp.get("/protocol")
def get_protocol():  # type: ignore[no-untyped-def]
    session = get_session()
    organization_id = default_organization_id(session)
    doctors = list(session.scalars(_doctor_query(organization_id)))
    locations = sorted(
        session.scalars(select(Location).where(Location.organization_id == organization_id)).all(),
        key=location_sort_key,
    )
    return jsonify(
        {
            "locations": [location_json(item) for item in locations],
            "doctors": [doctor_json(item) for item in doctors],
            "body_parts": list(BODY_PARTS),
            "issue_types": list(ISSUE_TYPES),
        }
    )
