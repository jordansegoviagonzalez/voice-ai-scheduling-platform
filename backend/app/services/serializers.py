from __future__ import annotations

from typing import Any

from app.models import Appointment, BookingConfirmation, Call, Doctor, Location, Patient, RoutingDecision, Slot


def patient_json(patient: Patient) -> dict[str, Any]:
    return {
        "id": patient.id,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "full_name": patient.full_name,
        "date_of_birth": patient.date_of_birth.isoformat(),
        "phone": patient.phone,
        "email": patient.email,
        "created_at": patient.created_at.isoformat(),
    }


def location_json(location: Location) -> dict[str, Any]:
    return {"id": location.id, "code": location.code, "name": location.name}


def doctor_json(doctor: Doctor) -> dict[str, Any]:
    return {
        "id": doctor.id,
        "first_name": doctor.first_name,
        "last_name": doctor.last_name,
        "full_name": doctor.full_name,
        "accepts_new_patients": doctor.accepts_new_patients,
        "active": doctor.active,
        "locations": [location_json(item) for item in sorted(doctor.locations, key=lambda x: x.id)],
        "capabilities": [
            {"body_part": item.body_part, "issue_type": item.issue_type}
            for item in sorted(doctor.capabilities, key=lambda x: (x.body_part, x.issue_type))
        ],
    }


def slot_json(slot: Slot) -> dict[str, Any]:
    return {
        "id": slot.id,
        "doctor": doctor_json(slot.doctor),
        "location": location_json(slot.location),
        "starts_at": slot.starts_at.isoformat(),
        "ends_at": slot.ends_at.isoformat(),
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
            "status": appointment.slot.status,
        },
        "body_part": appointment.body_part,
        "issue_type": appointment.issue_type,
        "status": appointment.status,
        "booking_source": appointment.booking_source,
        "call_id": appointment.call_id,
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
