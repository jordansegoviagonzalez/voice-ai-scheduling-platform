from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask.typing import ResponseReturnValue

from app.errors import ApiError
from app.extensions import get_session
from app.models import Patient
from app.routes.common import json_body
from app.services.patient_access_service import PatientAccessService
from app.services.serializers import patient_profile_json
from app.services.session_security import clear_patient_session, require_patient_session

patient_account_bp = Blueprint("patient_account", __name__, url_prefix="/api/patient")


@patient_account_bp.get("/profile")
def get_profile() -> ResponseReturnValue:
    patient = _authenticated_patient()
    return jsonify({"patient": patient_profile_json(patient)})


@patient_account_bp.patch("/profile")
def update_profile() -> ResponseReturnValue:
    patient = _authenticated_patient()
    data = json_body(request)
    read_only_fields = {
        "firstName",
        "first_name",
        "lastName",
        "last_name",
        "dateOfBirth",
        "date_of_birth",
        "insuranceProvider",
        "insurance_provider",
        "accountCreatedAt",
        "created_at",
        "patientId",
        "patient_id",
        "id",
    }
    attempted_read_only = sorted(field for field in read_only_fields if field in data)
    if attempted_read_only:
        raise ApiError(
            "VALIDATION_ERROR",
            "Only email and phone number can be updated.",
            422,
            {field: ["Read-only field"] for field in attempted_read_only},
        )
    email = _required_string(data, "email", max_length=255)
    phone = _required_string(data, "phone", "phoneNumber", max_length=32)
    updated = PatientAccessService(get_session()).update_contact(patient, email=email, phone=phone)
    return jsonify({"patient": patient_profile_json(updated)})


@patient_account_bp.post("/logout")
def logout_patient() -> ResponseReturnValue:
    clear_patient_session()
    return jsonify({"success": True})


def _authenticated_patient() -> Patient:
    patient_id = require_patient_session()
    patient = get_session().get(Patient, patient_id)
    if patient is None:
        clear_patient_session()
        raise ApiError("UNAUTHORIZED", "Valid patient session required", 401)
    return patient


def _required_string(data: dict[str, object], *names: str, max_length: int) -> str:
    for name in names:
        value = data.get(name)
        if value not in (None, ""):
            if not isinstance(value, str):
                raise ApiError("VALIDATION_ERROR", f"{name} must be a string.", 422, {name: ["Invalid string"]})
            cleaned = value.strip()
            if not cleaned:
                break
            if len(cleaned) > max_length:
                raise ApiError(
                    "FIELD_TOO_LONG",
                    f"{name} exceeds the maximum length.",
                    413,
                    {name: [f"Maximum length is {max_length} characters"]},
                )
            return cleaned
    field_name = names[0]
    raise ApiError("VALIDATION_ERROR", "Required fields are missing.", 422, {field_name: ["This field is required"]})
