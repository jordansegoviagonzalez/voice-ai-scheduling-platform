from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.organizations import organization_type_for_slug
from app.domain.locations import location_sort_key
from app.domain.specialties import is_general_orthopedics, primary_specialty
from app.models import (
    Appointment,
    BookingConfirmation,
    Call,
    Doctor,
    Location,
    Organization,
    Patient,
    RoutingDecision,
    Slot,
)
from app.models.chat import ChatSession


def organization_json(organization: Organization) -> dict[str, Any]:
    return {
        "id": organization.id,
        "slug": organization.slug,
        "name": organization.name,
        "organization_type": organization_type_for_slug(organization.slug),
        "doctor_count": len(organization.doctors),
        "status": organization.status,
        "timezone": organization.timezone,
        "active": organization.status == "ACTIVE",
        "created_at": organization.created_at.isoformat(),
        "updated_at": organization.updated_at.isoformat(),
    }


def public_organization_json(organization: Organization) -> dict[str, Any]:
    return {
        "id": organization.id,
        "slug": organization.slug,
        "name": organization.name,
        "organization_type": organization_type_for_slug(organization.slug),
        "status": organization.status,
        "timezone": organization.timezone,
    }


def patient_json(patient: Patient) -> dict[str, Any]:
    return {
        "id": patient.id,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "full_name": patient.full_name,
        "date_of_birth": patient.date_of_birth.isoformat(),
        "phone": patient.phone,
        "email": patient.email,
        "insurance_provider": patient.insurance_provider,
        "created_at": patient.created_at.isoformat(),
    }


def patient_profile_json(patient: Patient) -> dict[str, Any]:
    return {
        "firstName": patient.first_name,
        "lastName": patient.last_name,
        "fullName": patient.full_name,
        "dateOfBirth": patient.date_of_birth.isoformat(),
        "email": patient.email,
        "phone": patient.phone,
        "insuranceProvider": patient.insurance_provider,
        "accountCreatedAt": patient.created_at.isoformat(),
    }


def location_json(location: Location) -> dict[str, Any]:
    return {
        "id": location.id,
        "organization_id": location.organization_id,
        "code": location.code,
        "name": location.name,
    }


def doctor_json(doctor: Doctor) -> dict[str, Any]:
    return {
        "id": doctor.id,
        "organization_id": doctor.organization_id,
        "first_name": doctor.first_name,
        "last_name": doctor.last_name,
        "full_name": doctor.full_name,
        "primary_specialty": primary_specialty(doctor),
        "is_general_orthopedics": is_general_orthopedics(doctor),
        "accepts_new_patients": doctor.accepts_new_patients,
        "active": doctor.active,
        "locations": [location_json(item) for item in sorted(doctor.locations, key=location_sort_key)],
        "capabilities": [
            {"body_part": item.body_part, "issue_type": item.issue_type}
            for item in sorted(doctor.capabilities, key=lambda x: (x.body_part, x.issue_type))
        ],
    }


def slot_json(slot: Slot) -> dict[str, Any]:
    local_start = _as_clinic_time(slot.starts_at)
    local_end = _as_clinic_time(slot.ends_at)
    return {
        "id": slot.id,
        "doctor": doctor_json(slot.doctor),
        "location": location_json(slot.location),
        "starts_at": slot.starts_at.isoformat(),
        "ends_at": slot.ends_at.isoformat(),
        "time_zone": CLINIC_TIMEZONE_LABEL,
        "display_date": _display_date(local_start),
        "display_time": _display_time(local_start),
        "display_datetime": _display_datetime(local_start),
        "display_end_time": _display_time(local_end),
        "status": slot.status,
    }


def appointment_json(appointment: Appointment) -> dict[str, Any]:
    return {
        "id": appointment.id,
        "patient": patient_json(appointment.patient),
        "doctor": doctor_json(appointment.doctor),
        "location": location_json(appointment.location),
        "slot": {
            "id": appointment.slot.id,
            "starts_at": appointment.slot.starts_at.isoformat(),
            "ends_at": appointment.slot.ends_at.isoformat(),
            "time_zone": CLINIC_TIMEZONE_LABEL,
            "display_date": _display_date(_as_clinic_time(appointment.slot.starts_at)),
            "display_time": _display_time(_as_clinic_time(appointment.slot.starts_at)),
            "display_datetime": _display_datetime(_as_clinic_time(appointment.slot.starts_at)),
            "display_end_time": _display_time(_as_clinic_time(appointment.slot.ends_at)),
            "status": appointment.slot.status,
        },
        "body_part": appointment.body_part,
        "issue_type": appointment.issue_type,
        "status": appointment.status,
        "booking_source": appointment.booking_source,
        "call_id": appointment.call_id,
        "chat_session_id": getattr(appointment, "chat_session", None) and appointment.chat_session.id,
        "created_at": appointment.created_at.isoformat(),
    }


def booking_confirmation_json(confirmation: BookingConfirmation) -> dict[str, Any]:
    return {
        "id": confirmation.id,
        "confirmation_token": confirmation.confirmation_token,
        "call_id": confirmation.call_id,
        "patient_id": confirmation.patient_id,
        "slot_id": confirmation.slot_id,
        "doctor": doctor_json(confirmation.doctor),
        "location": location_json(confirmation.location),
        "body_part": confirmation.body_part,
        "issue_type": confirmation.issue_type,
        "starts_at": confirmation.starts_at.isoformat(),
        "ends_at": confirmation.ends_at.isoformat(),
        "status": confirmation.status,
        "source": confirmation.source,
        "confirmed_at": confirmation.confirmed_at.isoformat(),
        "expires_at": confirmation.expires_at.isoformat(),
        "used_at": confirmation.used_at.isoformat() if confirmation.used_at else None,
        "appointment_id": confirmation.appointment_id,
    }


def decision_json(decision: RoutingDecision) -> dict[str, Any]:
    return {
        "id": decision.id,
        "call_id": decision.call_id,
        "patient_id": decision.patient_id,
        "doctor": doctor_json(decision.doctor) if decision.doctor else None,
        "decision": decision.decision,
        "reason_code": decision.reason_code,
        "human_readable_reason": decision.human_readable_reason,
        "request_context": decision.request_context,
        "created_at": decision.created_at.isoformat(),
    }


def call_json(call: Call, *, detailed: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": call.id,
        "external_call_id": call.external_call_id,
        "status": call.status,
        "caller_phone": call.caller_phone,
        "patient_status": call.patient_status,
        "requested_body_part": call.requested_body_part,
        "requested_issue_type": call.requested_issue_type,
        "started_at": call.started_at.isoformat(),
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "patient": patient_json(call.patient) if call.patient else None,
        "preferred_doctor": doctor_json(call.preferred_doctor) if call.preferred_doctor else None,
        "preferred_location": location_json(call.preferred_location) if call.preferred_location else None,
        "appointment": appointment_json(call.appointment) if call.appointment else None,
        "failure_reason": call.failure_reason,
        "redirect_summary": call.redirect_summary,
        "created_at": call.created_at.isoformat(),
    }
    if detailed:
        payload["transcript"] = [
            {
                "id": turn.id,
                "sequence_number": turn.sequence_number,
                "speaker": turn.speaker,
                "text": turn.text,
                "occurred_at": turn.occurred_at.isoformat(),
            }
            for turn in call.transcript_turns
        ]
        payload["routing_decisions"] = [decision_json(item) for item in call.routing_decisions]
    return payload


def _as_clinic_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(CLINIC_TIMEZONE)


def _display_date(value: datetime) -> str:
    return f"{value:%b} {value.day}"


def _display_time(value: datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _display_datetime(value: datetime) -> str:
    return f"{value:%A}, {value:%B} {value.day} at {_display_time(value)}"


def chat_session_json(session: ChatSession, detailed: bool = False) -> dict[str, Any]:
    collected_data = dict(session.collected_data_json) if session.collected_data_json else {}

    duration_aliases = ["duration", "symptoms_duration", "issue_duration"]
    for alias in duration_aliases:
        if alias in collected_data:
            val = collected_data.pop(alias)
            if val and not collected_data.get("symptom_duration"):
                collected_data["symptom_duration"] = val

    payload: dict[str, Any] = {
        "id": session.id,
        "patient": patient_json(session.patient) if session.patient else None,
        "status": session.status,
        "current_step": session.current_step,
        "collected_data": collected_data,
        "routing_result": session.routing_result_json,
        "appointment_id": session.appointment_id,
        "appointment": appointment_json(session.appointment) if session.appointment else None,
        "escalation_type": session.escalation_type,
        "escalation_reason": session.escalation_reason,
        "escalation_trigger_message_id": session.escalation_trigger_message_id,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
    }
    if detailed:
        trigger_message = next(
            (message for message in session.messages if message.id == session.escalation_trigger_message_id),
            None,
        )
        payload["escalation_trigger_message"] = (
            {
                "id": trigger_message.id,
                "role": trigger_message.role,
                "content": trigger_message.content,
                "sequence_number": trigger_message.sequence_number,
                "created_at": trigger_message.created_at.isoformat(),
            }
            if trigger_message
            else None
        )
        payload["messages"] = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sequence_number": m.sequence_number,
                "created_at": m.created_at.isoformat(),
            }
            for m in sorted(session.messages, key=lambda x: x.sequence_number)
        ]
        payload["events"] = [
            {
                "id": e.id,
                "event_type": e.event_type,
                "event_data": e.event_data_json,
                "created_at": e.created_at.isoformat(),
            }
            for e in sorted(session.events, key=lambda x: x.created_at)
        ]
    return payload


CLINIC_TIMEZONE = ZoneInfo("America/Los_Angeles")
CLINIC_TIMEZONE_LABEL = "America/Los_Angeles"
