from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.normalization import normalize_date_of_birth, normalize_phone
from app.domain.routing import PhysicianRoutingService, RoutingRequest
from app.errors import ApiError
from app.extensions import get_session
from app.integrations.openai import OpenAIIntegrationError
from app.integrations.vogent.security import verify_shared_secret, verify_webhook_signature
from app.models import Call, Patient, TranscriptTurn
from app.routes.common import bounded_string, int_or_none, json_body, require_fields
from app.services.booking import BookingService
from app.services.confirmation import BookingConfirmationService
from app.services.conversation import ConversationOrchestrator
from app.services.idempotency import IdempotencyService
from app.services.integration_status import VOGENT_INTEGRATION, record_integration_result

bp = Blueprint("vogent", __name__)

TERMINAL_CALL_STATUSES = {"SCHEDULED", "FAILED", "ABANDONED", "REDIRECTED"}
FunctionHandler = Callable[[Session], tuple[dict[str, Any], int]]


def _require_function_secret() -> None:
    configured = current_app.config.get("VOGENT_FUNCTION_SECRET")
    if not configured:
        if current_app.config.get("APP_ENV") == "production":
            raise ApiError("VOGENT_NOT_CONFIGURED", "Vogent function authentication is not configured.", 503)
        return
    supplied = request.headers.get("X-Vogent-Function-Secret", "")
    if not verify_shared_secret(supplied, configured):
        raise ApiError("UNAUTHORIZED", "Invalid integration credentials.", 401)


def _idempotent_function_response(
    operation: str,
    payload: dict[str, Any],
    handler: FunctionHandler,
) -> tuple[Response, int]:
    session = get_session()
    service = IdempotencyService(session)
    started = service.begin_request(provider="vogent", operation=operation, payload=payload, request=request)
    if started.is_duplicate:
        assert started.duplicate_status_code is not None
        return jsonify(started.duplicate_response), started.duplicate_status_code
    response, status_code = handler(session)
    service.complete_request(started.log, response=response, status_code=status_code)
    session.commit()
    return jsonify(response), status_code


def _terminal_update_allowed(call: Call, next_status: str) -> bool:
    if call.status in TERMINAL_CALL_STATUSES:
        return next_status == call.status
    return True


def _in_production_live_context() -> bool:
    public_url = str(current_app.config.get("PUBLIC_APP_URL") or "")
    return current_app.config.get("APP_ENV") == "production" and public_url.startswith("https://")


@bp.post("/vogent/functions/patient-lookup")
def vogent_patient_lookup():  # type: ignore[no-untyped-def]
    _require_function_secret()
    payload = json_body(request)
    require_fields(payload, "phone", "date_of_birth")

    def handler(session):  # type: ignore[no-untyped-def]
        phone = normalize_phone(bounded_string(payload, "phone", max_length=32) or "")
        dob = normalize_date_of_birth(bounded_string(payload, "date_of_birth", max_length=64) or "")
        patient = session.scalar(select(Patient).where(Patient.phone == phone, Patient.date_of_birth == dob))
        return (
            {
                "found": patient is not None,
                "patient_id": patient.id if patient else None,
                "patient_name": patient.full_name if patient else None,
            },
            200,
        )

    return _idempotent_function_response("patient-lookup", payload, handler)


@bp.post("/vogent/functions/routing-recommendations")
def vogent_routing():  # type: ignore[no-untyped-def]
    _require_function_secret()
    payload = json_body(request)
    require_fields(payload, "patient_status", "body_part", "issue_type")

    def handler(session):  # type: ignore[no-untyped-def]
        call_id = int_or_none(payload.get("call_id"), "call_id")
        result = PhysicianRoutingService(session).recommend(
            RoutingRequest(
                patient_id=int_or_none(payload.get("patient_id"), "patient_id"),
                patient_status=bounded_string(payload, "patient_status", max_length=16) or "",
                body_part=bounded_string(payload, "body_part", max_length=32) or "",
                issue_type=bounded_string(payload, "issue_type", max_length=32) or "",
                preferred_doctor_id=int_or_none(payload.get("preferred_doctor_id"), "preferred_doctor_id"),
                preferred_location_id=int_or_none(payload.get("preferred_location_id"), "preferred_location_id"),
                call_id=call_id,
            ),
            persist=bool(call_id),
        )
        if call_id and result["recommended"] is None:
            call = session.get(Call, call_id)
            if call and call.status not in TERMINAL_CALL_STATUSES:
                call.status = "REDIRECTED"
                call.redirect_summary = result["caller_safe_summary"]
                call.ended_at = datetime.now(UTC)
        recommended = result["recommended"]
        return (
            {
                "summary": result["caller_safe_summary"],
                "recommended_doctor": recommended["doctor"]["full_name"] if recommended else None,
                "recommended_doctor_id": recommended["doctor"]["id"] if recommended else None,
                "available_slots": recommended["available_slots"][:3] if recommended else [],
                "alternatives": [
                    {
                        "doctor_id": item["doctor"]["id"],
                        "doctor_name": item["doctor"]["full_name"],
                        "slots": item["available_slots"][:2],
                    }
                    for item in result["ranked_recommendations"][1:3]
                ],
                "rejections": [
                    {
                        "doctor_name": item["doctor"]["full_name"],
                        "reason": item["reason"],
                    }
                    for item in result["rejected_doctors"]
                    if item["is_preferred_doctor"]
                ],
                "fallback_explanation": result["fallback_explanation"],
            },
            200,
        )

    return _idempotent_function_response("routing-recommendations", payload, handler)


@bp.post("/vogent/functions/interpret-intent")
def vogent_interpret_intent():  # type: ignore[no-untyped-def]
    _require_function_secret()
    payload = json_body(request)
    require_fields(payload, "raw_user_text")

    def handler(session):  # type: ignore[no-untyped-def]
        try:
            previous_state = payload.get("previous_state")
            raw_user_text = bounded_string(
                payload,
                "raw_user_text",
                max_length=int(current_app.config.get("RAW_USER_TEXT_MAX_LENGTH", 4000)),
            )
            result = ConversationOrchestrator(session, current_app).interpret(
                raw_user_text=raw_user_text or "",
                previous_state=previous_state if isinstance(previous_state, dict) else None,
                patient_id=int_or_none(payload.get("patient_id"), "patient_id"),
                call_id=int_or_none(payload.get("call_id"), "call_id"),
            )
        except OpenAIIntegrationError as error:
            raise ApiError(error.code, error.message, 503 if error.retryable else 502) from error
        return result, 200

    return _idempotent_function_response("interpret-intent", payload, handler)


@bp.post("/vogent/functions/confirm-slot")
def vogent_confirm_slot():  # type: ignore[no-untyped-def]
    _require_function_secret()
    payload = json_body(request)
    require_fields(payload, "call_id", "patient_id", "slot_id", "body_part", "issue_type")

    def handler(session):  # type: ignore[no-untyped-def]
        confirmation = BookingConfirmationService(session).confirm(
            call_id=int(payload["call_id"]),
            patient_id=int(payload["patient_id"]),
            slot_id=int(payload["slot_id"]),
            body_part=bounded_string(payload, "body_part", max_length=32) or "",
            issue_type=bounded_string(payload, "issue_type", max_length=32) or "",
            source="VOGENT",
        )
        return (
            {
                "confirmed": True,
                "confirmation_token": confirmation.confirmation_token,
                "doctor_name": confirmation.doctor.full_name,
                "location_name": confirmation.location.name,
                "starts_at": confirmation.starts_at.isoformat(),
                "expires_at": confirmation.expires_at.isoformat(),
            },
            201,
        )

    return _idempotent_function_response("confirm-slot", payload, handler)


@bp.post("/vogent/functions/book-appointment")
def vogent_book():  # type: ignore[no-untyped-def]
    _require_function_secret()
    payload = json_body(request)
    require_fields(payload, "patient_id", "slot_id", "body_part", "issue_type", "confirmation_token")

    def handler(session):  # type: ignore[no-untyped-def]
        appointment = BookingService(session).book(
            patient_id=int(payload["patient_id"]),
            slot_id=int(payload["slot_id"]),
            body_part=bounded_string(payload, "body_part", max_length=32) or "",
            issue_type=bounded_string(payload, "issue_type", max_length=32) or "",
            call_id=int_or_none(payload.get("call_id"), "call_id"),
            booking_source="VOGENT",
            confirmation_token=bounded_string(payload, "confirmation_token", max_length=128) or "",
        )
        return (
            {
                "booked": True,
                "appointment_id": appointment.id,
                "doctor_name": appointment.doctor.full_name,
                "location_name": appointment.location.name,
                "starts_at": appointment.slot.starts_at.isoformat(),
            },
            201,
        )

    return _idempotent_function_response("book-appointment", payload, handler)


@bp.post("/vogent/webhooks")
def vogent_webhooks():  # type: ignore[no-untyped-def]
    raw_body = request.get_data(cache=True)
    secret = current_app.config.get("VOGENT_WEBHOOK_SECRET")
    if secret:
        signature = request.headers.get("X-Elto-Signature", "")
        if not verify_webhook_signature(raw_body, signature, secret):
            raise ApiError("INVALID_WEBHOOK_SIGNATURE", "Invalid webhook signature.", 401)
    elif current_app.config.get("APP_ENV") == "production":
        raise ApiError("VOGENT_NOT_CONFIGURED", "Webhook verification is not configured.", 503)

    payload = json_body(request)
    event = payload.get("event")
    nested_payload = payload.get("payload")
    data: dict[str, Any] = nested_payload if isinstance(nested_payload, dict) else payload
    session = get_session()
    external_id = str(data.get("dial_id", "")) if data.get("dial_id") is not None else None
    idempotency = IdempotencyService(session)
    event_record = idempotency.record_event(
        provider="vogent",
        event_type=str(event),
        external_call_id=external_id,
        payload=payload,
    )
    if event_record.duplicate:
        session.commit()
        if event == "dial.inbound" and external_id:
            call = session.scalar(select(Call).where(Call.external_call_id == external_id))
            if call is not None:
                return jsonify(
                    {
                        "call_agent_input": {"internal_call_id": str(call.id)},
                        "keywords": [],
                        "duplicate": True,
                    }
                )
        return jsonify({"received": True, "duplicate": True})

    if event == "dial.inbound":
        if not external_id:
            raise ApiError("VOGENT_DIAL_ID_REQUIRED", "dial.inbound payload requires dial_id.", 422)
        call = session.scalar(select(Call).where(Call.external_call_id == external_id))
        if call is None:
            call = Call(
                external_call_id=external_id,
                status="IN_PROGRESS",
                caller_phone=str(data.get("source_number", "unknown")),
                started_at=datetime.now(UTC),
                transcript=[],
            )
            session.add(call)
        idempotency.mark_event_processed(event_record.log)
        if _in_production_live_context():
            record_integration_result(
                session,
                integration_name=VOGENT_INTEGRATION,
                status="connected",
                detail="Latest signed Vogent inbound webhook was accepted.",
                metadata={"event": "dial.inbound"},
                success=True,
            )
        session.commit()
        return jsonify({"call_agent_input": {"internal_call_id": str(call.id)}, "keywords": []})

    external_id = str(data.get("dial_id", ""))
    call = session.scalar(select(Call).where(Call.external_call_id == external_id))
    if call is None:
        raise ApiError("CALL_NOT_FOUND", "No call record matches this Vogent dial.", 404)

    if event == "dial.updated":
        status_map = {
            "queued": "IN_PROGRESS",
            "ringing": "IN_PROGRESS",
            "in-progress": "IN_PROGRESS",
            "completed": "SCHEDULED" if call.appointment_id else "ABANDONED",
            "failed": "FAILED",
            "canceled": "ABANDONED",
            "busy": "ABANDONED",
            "no-answer": "ABANDONED",
        }
        dial_status = str(data.get("status", ""))
        next_status = status_map.get(dial_status, call.status)
        if _terminal_update_allowed(call, next_status):
            call.status = next_status
        if dial_status in {"completed", "failed", "canceled", "busy", "no-answer"}:
            call.ended_at = datetime.now(UTC)
    elif event == "dial.transcript":
        turns = data.get("transcript", [])
        if not isinstance(turns, list):
            raise ApiError("VALIDATION_ERROR", "dial.transcript payload requires a transcript array.", 422)
        max_turns = int(current_app.config.get("TRANSCRIPT_TURN_MAX_COUNT", 200))
        if len(turns) > max_turns:
            raise ApiError(
                "TRANSCRIPT_TOO_LARGE",
                "The transcript contains too many turns.",
                413,
                {"transcript": [f"Maximum turn count is {max_turns}"]},
            )
        call.transcript_turns.clear()
        call.transcript = []
        for index, turn in enumerate(turns, start=1):
            if not isinstance(turn, dict):
                raise ApiError("VALIDATION_ERROR", "Each transcript turn must be an object.", 422)
            text = bounded_string(
                turn,
                "text",
                max_length=int(current_app.config.get("TRANSCRIPT_TURN_MAX_LENGTH", 2000)),
            )
            speaker_value = bounded_string(turn, "speaker", max_length=16, required=False)
            speaker = "AI" if (speaker_value or "").upper() == "AI" else "HUMAN"
            occurred_at = datetime.now(UTC)
            call.transcript_turns.append(
                TranscriptTurn(
                    sequence_number=index,
                    speaker=speaker,
                    text=text or "",
                    occurred_at=occurred_at,
                )
            )
            call.transcript.append(
                {
                    "sequence_number": index,
                    "speaker": speaker,
                    "text": text or "",
                    "occurred_at": occurred_at.isoformat(),
                }
            )
    idempotency.mark_event_processed(event_record.log)
    session.commit()
    return jsonify({"received": True})
