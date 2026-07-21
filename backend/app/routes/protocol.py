from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.errors import ApiError
from app.extensions import get_session
from app.models import Doctor, Location
from app.services.serializers import doctor_json, location_json

bp = Blueprint("protocol", __name__)


def _doctor_query():  # type: ignore[no-untyped-def]
    return (
        select(Doctor)
        .options(selectinload(Doctor.locations), selectinload(Doctor.capabilities))
        .order_by(Doctor.last_name, Doctor.first_name)
    )


@bp.get("/doctors")
def list_doctors():  # type: ignore[no-untyped-def]
    doctors = list(get_session().scalars(_doctor_query()))
    return jsonify({"doctors": [doctor_json(item) for item in doctors]})


@bp.get("/doctors/<int:doctor_id>")
def get_doctor(doctor_id: int):  # type: ignore[no-untyped-def]
    doctor = get_session().scalar(_doctor_query().where(Doctor.id == doctor_id))
    if doctor is None:
        raise ApiError("DOCTOR_NOT_FOUND", "Physician was not found.", 404)
    return jsonify({"doctor": doctor_json(doctor)})


@bp.get("/locations")
def list_locations():  # type: ignore[no-untyped-def]
    locations = list(get_session().scalars(select(Location).order_by(Location.id)))
    return jsonify({"locations": [location_json(item) for item in locations]})


@bp.get("/protocol")
def get_protocol():  # type: ignore[no-untyped-def]
    doctors = list(get_session().scalars(_doctor_query()))
    locations = list(get_session().scalars(select(Location).order_by(Location.id)))
    return jsonify(
        {
            "locations": [location_json(item) for item in locations],
            "doctors": [doctor_json(item) for item in doctors],
            "body_parts": ["Knee", "Hip", "Shoulder", "Hand/Wrist", "Foot/Ankle", "Spine"],
            "issue_types": ["Fracture", "Joint Replacement", "Sports Medicine", "General"],
        }
    )
