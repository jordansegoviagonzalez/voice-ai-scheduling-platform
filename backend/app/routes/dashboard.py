from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import Blueprint, current_app, jsonify
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.errors import ApiError
from app.extensions import get_session
from app.models import Appointment, Call, Doctor, Patient, RoutingDecision, Slot
from app.models.chat import ChatSession
from app.routes.auth import require_admin_session
from app.services.integration_status import build_integration_statuses
from app.services.organization_context import default_organization_id
from app.services.serializers import appointment_json, call_json, chat_session_json, decision_json, patient_json

bp = Blueprint("dashboard", __name__)


@bp.get("/dashboard/overview")
def overview():  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    organization_id = default_organization_id(session)
    since = datetime.now(UTC) - timedelta(days=30)
    rows = session.execute(
        select(Call.status, func.count(Call.id))
        .where(Call.organization_id == organization_id, Call.started_at >= since)
        .group_by(Call.status)
    ).all()
    counts: dict[str, int] = {str(status): int(count) for status, count in rows}
    total = sum(counts.values())
    scheduled = counts.get("SCHEDULED", 0)
    recent_calls = list(
        session.scalars(
            select(Call)
            .where(Call.organization_id == organization_id)
            .options(
                selectinload(Call.patient),
                selectinload(Call.preferred_doctor).selectinload(Doctor.locations),
                selectinload(Call.preferred_doctor).selectinload(Doctor.capabilities),
                selectinload(Call.preferred_location),
                selectinload(Call.appointment).selectinload(Appointment.patient),
                selectinload(Call.appointment).selectinload(Appointment.location),
                selectinload(Call.appointment).selectinload(Appointment.slot),
                selectinload(Call.appointment).selectinload(Appointment.doctor).selectinload(Doctor.locations),
                selectinload(Call.appointment).selectinload(Appointment.doctor).selectinload(Doctor.capabilities),
                selectinload(Call.appointment).selectinload(Appointment.chat_session),
            )
            .order_by(Call.started_at.desc())
            .limit(6)
        )
    )
    recent_web_chats = list(
        session.scalars(
            select(ChatSession)
            .where(ChatSession.organization_id == organization_id)
            .options(
                selectinload(ChatSession.patient),
                selectinload(ChatSession.appointment).selectinload(Appointment.doctor),
            )
            .order_by(ChatSession.created_at.desc())
            .limit(6)
        )
    )
    upcoming = list(
        session.scalars(
            select(Appointment)
            .join(Appointment.slot)
            .where(Appointment.organization_id == organization_id, Appointment.status == "SCHEDULED")
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.doctor).selectinload(Doctor.locations),
                selectinload(Appointment.doctor).selectinload(Doctor.capabilities),
                selectinload(Appointment.location),
                selectinload(Appointment.slot),
                selectinload(Appointment.chat_session),
            )
            .order_by(Slot.starts_at)
            .limit(6)
        )
    )
    exceptions = list(
        session.scalars(
            select(RoutingDecision)
            .where(RoutingDecision.organization_id == organization_id, RoutingDecision.decision == "REJECTED")
            .options(
                selectinload(RoutingDecision.doctor).selectinload(Doctor.locations),
                selectinload(RoutingDecision.doctor).selectinload(Doctor.capabilities),
            )
            .order_by(RoutingDecision.created_at.desc())
            .limit(6)
        )
    )
    return jsonify(
        {
            "metrics": {
                "total_calls": total,
                "scheduled": scheduled,
                "redirected": counts.get("REDIRECTED", 0),
                "abandoned": counts.get("ABANDONED", 0),
                "failed": counts.get("FAILED", 0),
                "in_progress": counts.get("IN_PROGRESS", 0),
                "conversion_rate": round((scheduled / total * 100), 1) if total else 0,
            },
            "outcomes": [{"status": status, "count": count} for status, count in sorted(counts.items())],
            "recent_calls": [call_json(item) for item in recent_calls],
            "recent_web_chats": [chat_session_json(item) for item in recent_web_chats],
            "upcoming_appointments": [appointment_json(item) for item in upcoming],
            "routing_exceptions": [decision_json(item) for item in exceptions],
            "integration_statuses": build_integration_statuses(current_app, session),
        }
    )


@bp.get("/routing-audit")
def routing_audit():  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    organization_id = default_organization_id(session)
    decisions = list(
        session.scalars(
            select(RoutingDecision)
            .where(RoutingDecision.organization_id == organization_id)
            .options(
                selectinload(RoutingDecision.doctor).selectinload(Doctor.locations),
                selectinload(RoutingDecision.doctor).selectinload(Doctor.capabilities),
            )
            .order_by(RoutingDecision.created_at.desc())
            .limit(250)
        )
    )
    return jsonify({"decisions": [decision_json(item) for item in decisions]})


@bp.get("/dashboard/chat-sessions")
def list_chat_sessions():  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    organization_id = default_organization_id(session)
    sessions = session.scalars(
        select(ChatSession)
        .where(ChatSession.organization_id == organization_id)
        .options(
            selectinload(ChatSession.patient),
            selectinload(ChatSession.appointment).selectinload(Appointment.patient),
            selectinload(ChatSession.appointment).selectinload(Appointment.doctor).selectinload(Doctor.locations),
            selectinload(ChatSession.appointment).selectinload(Appointment.doctor).selectinload(Doctor.capabilities),
            selectinload(ChatSession.appointment).selectinload(Appointment.location),
            selectinload(ChatSession.appointment).selectinload(Appointment.slot),
        )
        .order_by(ChatSession.created_at.desc())
    ).all()
    return jsonify({"chat_sessions": [chat_session_json(s) for s in sessions]})


@bp.get("/dashboard/chat-sessions/<int:session_id>")
def get_chat_session(session_id: int):  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    chat_session = session.scalar(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.organization_id == default_organization_id(session))
        .options(
            selectinload(ChatSession.patient),
            selectinload(ChatSession.messages),
            selectinload(ChatSession.events),
            selectinload(ChatSession.appointment).selectinload(Appointment.patient),
            selectinload(ChatSession.appointment).selectinload(Appointment.doctor).selectinload(Doctor.locations),
            selectinload(ChatSession.appointment).selectinload(Appointment.doctor).selectinload(Doctor.capabilities),
            selectinload(ChatSession.appointment).selectinload(Appointment.location),
            selectinload(ChatSession.appointment).selectinload(Appointment.slot),
        )
    )
    if not chat_session:
        raise ApiError("NOT_FOUND", "Session not found", 404)
    return jsonify({"chat_session": chat_session_json(chat_session, detailed=True)})


@bp.get("/dashboard/patients")
def list_patients():  # type: ignore[no-untyped-def]
    require_admin_session()
    db_session = get_session()
    organization_id = default_organization_id(db_session)
    patients = db_session.scalars(select(Patient).order_by(Patient.last_name, Patient.first_name)).all()
    rows = []
    for patient in patients:
        payload = patient_json(patient)
        latest_appointment = db_session.scalar(
            select(Appointment)
            .where(Appointment.organization_id == organization_id, Appointment.patient_id == patient.id)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.doctor).selectinload(Doctor.locations),
                selectinload(Appointment.doctor).selectinload(Doctor.capabilities),
                selectinload(Appointment.location),
                selectinload(Appointment.slot),
            )
            .order_by(Appointment.created_at.desc())
            .limit(1)
        )
        latest_chat = db_session.scalar(
            select(ChatSession)
            .where(ChatSession.organization_id == organization_id, ChatSession.patient_id == patient.id)
            .order_by(ChatSession.updated_at.desc())
            .limit(1)
        )
        payload["latest_appointment"] = appointment_json(latest_appointment) if latest_appointment else None
        payload["latest_chat_status"] = latest_chat.status if latest_chat else None
        rows.append(payload)
    return jsonify({"patients": rows})


@bp.get("/dashboard/patients/<int:patient_id>")
def get_dashboard_patient(patient_id: int):  # type: ignore[no-untyped-def]
    require_admin_session()
    db_session = get_session()
    organization_id = default_organization_id(db_session)
    patient = db_session.get(Patient, patient_id)
    if not patient:
        raise ApiError("NOT_FOUND", "Patient not found", 404)

    appointments = db_session.scalars(
        select(Appointment)
        .where(Appointment.organization_id == organization_id, Appointment.patient_id == patient_id)
        .options(
            selectinload(Appointment.doctor).selectinload(Doctor.locations),
            selectinload(Appointment.location),
            selectinload(Appointment.slot),
        )
        .order_by(Appointment.created_at.desc())
    ).all()

    chat_sessions = db_session.scalars(
        select(ChatSession)
        .where(ChatSession.organization_id == organization_id, ChatSession.patient_id == patient_id)
        .order_by(ChatSession.created_at.desc())
    ).all()

    calls = db_session.scalars(
        select(Call)
        .where(Call.organization_id == organization_id, Call.patient_id == patient_id)
        .order_by(Call.started_at.desc())
    ).all()

    return jsonify(
        {
            "patient": patient_json(patient),
            "appointments": [appointment_json(a) for a in appointments],
            "chat_sessions": [chat_session_json(s) for s in chat_sessions],
            "calls": [call_json(c) for c in calls],
        }
    )
