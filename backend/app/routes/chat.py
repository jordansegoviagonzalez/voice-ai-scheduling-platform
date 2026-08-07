from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from app.domain.routing import PhysicianRoutingService
from app.errors import ApiError
from app.extensions import get_session as get_db_session
from app.infrastructure.ai.structured_intake import OpenAIIntakeClient
from app.models import ChatSession, Patient
from app.routes.common import json_body
from app.services.ai_intake_service import AIIntakeService
from app.services.booking import BookingService
from app.services.chat_session_service import ChatSessionService
from app.services.chat_workflow_service import ChatWorkflowService
from app.services.escalation_service import EscalationService
from app.services.organization_context import default_organization_id, explicit_organization_id_from_slug
from app.services.patient_access_service import PatientAccessService
from app.services.session_security import (
    has_patient_session,
    remember_patient_chat_session,
    remembered_patient_chat_session_ids,
    require_patient_session,
    start_patient_session,
    touch_patient_session,
)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


def get_services(organization_slug: str | None = None) -> tuple[ChatSessionService, ChatWorkflowService]:
    db_session = get_db_session()
    organization_id = (
        explicit_organization_id_from_slug(db_session, organization_slug)
        if organization_slug is not None
        else default_organization_id(db_session)
    )
    chat_service = ChatSessionService(db_session)
    ai_client = OpenAIIntakeClient(
        current_app.config.get("OPENAI_API_KEY"),
        str(current_app.config.get("OPENAI_MODEL", "gpt-5.2")),
        timeout_seconds=float(current_app.config.get("OPENAI_TIMEOUT_SECONDS", 8)),
        max_retries=int(current_app.config.get("OPENAI_MAX_RETRIES", 2)),
    )
    workflow = ChatWorkflowService(
        organization_id=organization_id,
        db_session=db_session,
        chat_service=chat_service,
        patient_access=PatientAccessService(db_session),
        ai_intake=AIIntakeService(ai_client),
        escalation=EscalationService(chat_service),
        routing=PhysicianRoutingService(db_session),
        booking=BookingService(db_session),
    )
    return chat_service, workflow


@chat_bp.route("/sessions", methods=["POST"])
def create_session() -> ResponseReturnValue:
    return _create_session()


@chat_bp.route("/organizations/<organization_slug>/sessions", methods=["POST"])
def create_organization_session(organization_slug: str) -> ResponseReturnValue:
    return _create_session(organization_slug)


def _create_session(organization_slug: str | None = None) -> ResponseReturnValue:
    data = json_body(request)
    patient_mode = data.get("patientMode")
    if patient_mode not in {"new", "returning"}:
        raise ApiError("VALIDATION_ERROR", "patientMode must be new or returning.", 422)

    chat_service, workflow = get_services(organization_slug)
    if patient_mode == "returning":
        patient = workflow.patient_access.verify_returning_patient(
            organization_id=workflow.organization_id,
            email=_string_field(data, "email", max_length=255),
            password=_password_field(data, "password", required=True),
        )
        payload, status = _patient_session_payload(chat_service, workflow, patient, "returning")
        return jsonify(payload), status

    patient = _register_new_patient(workflow, data)
    payload, status = _patient_session_payload(chat_service, workflow, patient, "new")
    return jsonify(payload), status


@chat_bp.route("/sessions/access", methods=["POST"])
def create_access_session() -> ResponseReturnValue:
    return _create_access_session()


@chat_bp.route("/organizations/<organization_slug>/sessions/access", methods=["POST"])
def create_organization_access_session(organization_slug: str) -> ResponseReturnValue:
    return _create_access_session(organization_slug)


def _create_access_session(organization_slug: str | None = None) -> ResponseReturnValue:
    data = json_body(request)
    patient_mode = data.get("patientMode")
    if patient_mode != "returning":
        raise ApiError("VALIDATION_ERROR", "patientMode must be returning.", 422)

    chat_service, workflow = get_services(organization_slug)
    chat_session = chat_service.create_session(organization_id=workflow.organization_id, patient_mode="returning")
    _remember_session(chat_session.id)
    payload = workflow._session_payload(workflow._session_or_404(chat_session.id))
    if payload["messages"]:
        payload["assistantMessage"] = payload["messages"][-1]
    return jsonify(payload), 201


@chat_bp.route("/sessions/<int:session_id>/patient-access", methods=["POST"])
def patient_access(session_id: int) -> ResponseReturnValue:
    return _patient_access(session_id)


@chat_bp.route("/organizations/<organization_slug>/sessions/<int:session_id>/patient-access", methods=["POST"])
def organization_patient_access(organization_slug: str, session_id: int) -> ResponseReturnValue:
    return _patient_access(session_id, organization_slug)


def _patient_access(session_id: int, organization_slug: str | None = None) -> ResponseReturnValue:
    _require_session_access(session_id)
    _, workflow = get_services(organization_slug)
    payload = workflow.authenticate_returning_patient(session_id, request.json or {})
    return jsonify(payload)


@chat_bp.route("/sessions/<int:session_id>/messages", methods=["POST"])
def handle_message(session_id: int) -> ResponseReturnValue:
    return _handle_message(session_id)


@chat_bp.route("/organizations/<organization_slug>/sessions/<int:session_id>/messages", methods=["POST"])
def organization_handle_message(organization_slug: str, session_id: int) -> ResponseReturnValue:
    return _handle_message(session_id, organization_slug)


def _handle_message(session_id: int, organization_slug: str | None = None) -> ResponseReturnValue:
    _require_session_access(session_id)
    _, workflow = get_services(organization_slug)
    payload = workflow.handle_message(session_id, (request.json or {}).get("message", ""))
    return jsonify(payload)


@chat_bp.route("/sessions/<int:session_id>", methods=["GET"])
def get_session(session_id: int) -> ResponseReturnValue:
    return _get_session(session_id)


@chat_bp.route("/organizations/<organization_slug>/sessions/<int:session_id>", methods=["GET"])
def get_organization_session(organization_slug: str, session_id: int) -> ResponseReturnValue:
    return _get_session(session_id, organization_slug)


def _get_session(session_id: int, organization_slug: str | None = None) -> ResponseReturnValue:
    _require_session_access(session_id)
    _, workflow = get_services(organization_slug)
    return jsonify(workflow._session_payload(workflow._session_or_404(session_id)))


@chat_bp.route("/sessions/<int:session_id>/appointments/select", methods=["POST"])
def select_appointment(session_id: int) -> ResponseReturnValue:
    return _select_appointment(session_id)


@chat_bp.route("/organizations/<organization_slug>/sessions/<int:session_id>/appointments/select", methods=["POST"])
def select_organization_appointment(organization_slug: str, session_id: int) -> ResponseReturnValue:
    return _select_appointment(session_id, organization_slug)


def _select_appointment(session_id: int, organization_slug: str | None = None) -> ResponseReturnValue:
    _require_session_access(session_id)
    slot_id = (request.json or {}).get("slotId")
    if not isinstance(slot_id, int):
        raise ApiError("VALIDATION_ERROR", "slotId is required.", 422, {"slotId": ["Required integer"]})
    _, workflow = get_services(organization_slug)
    payload = workflow.select_appointment(session_id, slot_id)
    return jsonify(payload), 200


@chat_bp.route("/sessions/<int:session_id>/appointments/confirm", methods=["POST"])
def confirm_appointment(session_id: int) -> ResponseReturnValue:
    return _confirm_appointment(session_id)


@chat_bp.route("/organizations/<organization_slug>/sessions/<int:session_id>/appointments/confirm", methods=["POST"])
def confirm_organization_appointment(organization_slug: str, session_id: int) -> ResponseReturnValue:
    return _confirm_appointment(session_id, organization_slug)


def _confirm_appointment(session_id: int, organization_slug: str | None = None) -> ResponseReturnValue:
    _require_session_access(session_id)
    _, workflow = get_services(organization_slug)
    payload, status = workflow.confirm_appointment(session_id)
    return jsonify(payload), status


def _remember_session(session_id: int) -> None:
    remember_patient_chat_session(session_id)


def _require_session_access(session_id: int) -> None:
    ids = set(remembered_patient_chat_session_ids())
    if session_id not in ids:
        raise ApiError("UNAUTHORIZED", "This chat session is not available in the current browser session.", 401)
    chat_session = get_db_session().get(ChatSession, session_id)
    if chat_session and chat_session.patient_id is not None:
        if has_patient_session():
            patient_id = require_patient_session(refresh=False)
            if chat_session.patient_id != patient_id:
                raise ApiError(
                    "UNAUTHORIZED",
                    "This chat session is not available in the current browser session.",
                    401,
                )
            touch_patient_session()
            return
        start_patient_session(chat_session.patient_id)
        return
    if has_patient_session():
        require_patient_session(refresh=False)
        touch_patient_session()


def _patient_session_payload(
    chat_service: ChatSessionService,
    workflow: ChatWorkflowService,
    patient: Patient,
    patient_type: str,
) -> tuple[dict[str, object], int]:
    start_patient_session(patient.id)
    existing = chat_service.find_latest_resumable_patient_session(
        organization_id=workflow.organization_id,
        patient_id=patient.id,
    )
    if existing is None:
        existing = chat_service.find_patient_session(
            organization_id=workflow.organization_id,
            session_ids=remembered_patient_chat_session_ids(),
            patient_id=patient.id,
            patient_type=patient_type,
        )
    status = 200
    if existing is None:
        existing = chat_service.create_patient_session(
            organization_id=workflow.organization_id,
            patient=patient,
            patient_type=patient_type,
        )
        _remember_session(existing.id)
        status = 201
    else:
        _remember_session(existing.id)

    payload = workflow._session_payload(workflow._session_or_404(existing.id))
    if payload["messages"]:
        payload["assistantMessage"] = payload["messages"][-1]
    return payload, status


def _register_new_patient(workflow: ChatWorkflowService, data: dict[str, object]) -> Patient:
    first_name = _string_field(data, "firstName", "first_name", max_length=100)
    last_name = _string_field(data, "lastName", "last_name", max_length=100)
    date_of_birth = _string_field(data, "dateOfBirth", "date_of_birth", max_length=32)
    phone = _string_field(data, "phone", "contactNumber", "contact_number", max_length=32)
    email = _string_field(data, "email", max_length=255)
    insurance_provider = _string_field(data, "insuranceProvider", "insurance_provider", max_length=255)
    patient, _ = workflow.patient_access.create_or_get_new_patient(
        organization_id=workflow.organization_id,
        full_name=f"{first_name} {last_name}",
        date_of_birth=date_of_birth,
        phone=phone,
        email=email,
        insurance_provider=insurance_provider,
        password=_password_field(data, "password", required=True),
        password_confirmation=_password_field(
            data,
            "confirmPassword",
            "passwordConfirmation",
            "confirm_password",
            required=True,
        ),
    )
    return patient


def _string_field(data: dict[str, object], *names: str, max_length: int) -> str:
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


def _password_field(data: dict[str, object], *names: str, required: bool) -> object:
    for name in names:
        value = data.get(name)
        if value is not None:
            if value == "" and required:
                break
            if not isinstance(value, str):
                raise ApiError("VALIDATION_ERROR", f"{name} must be a string.", 422, {name: ["Invalid string"]})
            return value
    field_name = names[0]
    if required:
        raise ApiError(
            "VALIDATION_ERROR", "Required fields are missing.", 422, {field_name: ["This field is required"]}
        )
    return None
