from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.domain.normalization import normalize_phone
from app.errors import ApiError
from app.extensions import get_session
from app.models import Appointment, Doctor, Patient
from app.routes.common import bounded_string, json_body, parse_date, require_fields
from app.services.serializers import appointment_json, patient_json

bp = Blueprint("patients", __name__)


@bp.post("/patients/lookup")
def lookup_patient():  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(payload, "phone", "date_of_birth")
    phone = normalize_phone(bounded_string(payload, "phone", max_length=32) or "")
    dob = parse_date(bounded_string(payload, "date_of_birth", max_length=10) or "", "date_of_birth")
    patient = get_session().scalar(select(Patient).where(Patient.phone == phone, Patient.date_of_birth == dob))
    if patient is None:
        return jsonify({"found": False, "patient": None})
    return jsonify({"found": True, "patient": patient_json(patient)})


@bp.post("/patients")
def create_patient():  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(payload, "first_name", "last_name", "phone", "date_of_birth")
    session = get_session()
    first_name = bounded_string(payload, "first_name", max_length=100) or ""
    last_name = bounded_string(payload, "last_name", max_length=100) or ""
    phone = normalize_phone(bounded_string(payload, "phone", max_length=32) or "")
    dob = parse_date(bounded_string(payload, "date_of_birth", max_length=10) or "", "date_of_birth")
    email = bounded_string(payload, "email", max_length=255, required=False)
    existing = session.scalar(select(Patient).where(Patient.phone == phone, Patient.date_of_birth == dob))
    if existing:
        return jsonify({"created": False, "patient": patient_json(existing)}), 200
    patient = Patient(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        date_of_birth=dob,
        email=email,
    )
    session.add(patient)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApiError("DUPLICATE_PATIENT", "A patient with this phone and birth date exists.", 409) from error
    return jsonify({"created": True, "patient": patient_json(patient)}), 201


@bp.get("/patients/<int:patient_id>")
def get_patient(patient_id: int):  # type: ignore[no-untyped-def]
    patient = get_session().get(Patient, patient_id)
    if patient is None:
        raise ApiError("PATIENT_NOT_FOUND", "Patient was not found.", 404)
    return jsonify({"patient": patient_json(patient)})


@bp.get("/patients/<int:patient_id>/appointments")
def get_patient_appointments(patient_id: int):  # type: ignore[no-untyped-def]
    session = get_session()
    if session.get(Patient, patient_id) is None:
        raise ApiError("PATIENT_NOT_FOUND", "Patient was not found.", 404)
    appointments = list(
        session.scalars(
            select(Appointment)
            .where(Appointment.patient_id == patient_id)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.doctor).selectinload(Doctor.locations),
                selectinload(Appointment.doctor).selectinload(Doctor.capabilities),
                selectinload(Appointment.location),
                selectinload(Appointment.slot),
            )
            .order_by(Appointment.created_at.desc())
        )
    )
    return jsonify({"appointments": [appointment_json(item) for item in appointments]})
