from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import Blueprint, current_app, jsonify
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.extensions import get_session
from app.models import Appointment, Call, Doctor, RoutingDecision, Slot
from app.services.integration_status import build_integration_statuses
from app.services.serializers import appointment_json, call_json, decision_json

bp = Blueprint("dashboard", __name__)


@bp.get("/dashboard/overview")
def overview():  # type: ignore[no-untyped-def]
    session = get_session()
    since = datetime.now(UTC) - timedelta(days=30)
    rows = session.execute(
        select(Call.status, func.count(Call.id)).where(Call.started_at >= since).group_by(Call.status)
    ).all()
    counts: dict[str, int] = {str(status): int(count) for status, count in rows}
    total = sum(counts.values())
    scheduled = counts.get("SCHEDULED", 0)
    recent_calls = list(
        session.scalars(
            select(Call)
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
            )
            .order_by(Call.started_at.desc())
            .limit(6)
        )
    )
    upcoming = list(
        session.scalars(
            select(Appointment)
            .join(Appointment.slot)
            .where(Appointment.status == "SCHEDULED")
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.doctor).selectinload(Doctor.locations),
                selectinload(Appointment.doctor).selectinload(Doctor.capabilities),
                selectinload(Appointment.location),
                selectinload(Appointment.slot),
            )
            .order_by(Slot.starts_at)
            .limit(6)
        )
    )
    exceptions = list(
        session.scalars(
            select(RoutingDecision)
            .where(RoutingDecision.decision == "REJECTED")
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
            "upcoming_appointments": [appointment_json(item) for item in upcoming],
            "routing_exceptions": [decision_json(item) for item in exceptions],
            "integration_statuses": build_integration_statuses(current_app, session),
        }
    )


@bp.get("/routing-audit")
def routing_audit():  # type: ignore[no-untyped-def]
    decisions = list(
        get_session().scalars(
            select(RoutingDecision)
            .options(
                selectinload(RoutingDecision.doctor).selectinload(Doctor.locations),
                selectinload(RoutingDecision.doctor).selectinload(Doctor.capabilities),
            )
            .order_by(RoutingDecision.created_at.desc())
            .limit(250)
        )
    )
    return jsonify({"decisions": [decision_json(item) for item in decisions]})
