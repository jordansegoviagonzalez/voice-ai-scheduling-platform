from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.errors import ApiError
from app.extensions import get_session
from app.integrations.openai import OpenAIIntegrationError
from app.routes.common import bounded_string, int_or_none, json_body, require_fields
from app.services.conversation import ConversationOrchestrator

bp = Blueprint("conversation", __name__)


@bp.post("/conversation/interpret")
def interpret_conversation():  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(payload, "raw_user_text")
    raw_user_text = bounded_string(
        payload,
        "raw_user_text",
        max_length=int(current_app.config.get("RAW_USER_TEXT_MAX_LENGTH", 4000)),
    )
    session = get_session()
    previous_state = payload.get("previous_state")
    if previous_state is not None and not isinstance(previous_state, dict):
        raise ApiError("VALIDATION_ERROR", "previous_state must be an object.", 422)
    try:
        result = ConversationOrchestrator(session, current_app).interpret(
            raw_user_text=raw_user_text or "",
            previous_state=previous_state,
            patient_id=int_or_none(payload.get("patient_id"), "patient_id"),
            call_id=int_or_none(payload.get("call_id"), "call_id"),
        )
        session.commit()
        return jsonify(result)
    except OpenAIIntegrationError as error:
        session.rollback()
        status_code = 429 if error.code == "OPENAI_RATE_LIMITED" else 503 if error.retryable else 502
        if error.code in {"OPENAI_API_KEY_MISSING", "OPENAI_MODEL_MISMATCH", "OPENAI_MODE_INVALID"}:
            status_code = 503
        raise ApiError(error.code, error.message, status_code) from error
