from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.domain.normalization import BODY_PARTS, ISSUE_TYPES, normalize_body_part, normalize_issue_type
from app.integrations.openai.errors import OpenAIIntegrationError

PATIENT_STATUSES = {"NEW", "RETURNING", "UNKNOWN"}
DEFAULT_LOCATION_CODES = {"MAIN", "NORTH", "WEST"}
INTENT_FIELDS = {
    "raw_user_text",
    "patient_status",
    "body_part",
    "issue_type",
    "preferred_doctor_name",
    "preferred_location_code",
    "clarification_required",
    "clarification_question",
    "caller_correction",
}
CORRECTION_FIELDS = {
    "patient_status",
    "body_part",
    "issue_type",
    "preferred_doctor_name",
    "preferred_location_code",
}


@dataclass(frozen=True)
class StructuredIntent:
    raw_user_text: str
    patient_status: str
    body_part: str | None
    issue_type: str | None
    preferred_doctor_name: str | None
    preferred_location_code: str | None
    clarification_required: bool
    clarification_question: str | None
    caller_correction: dict[str, str | None]


STRUCTURED_INTENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "raw_user_text": {"type": "string"},
        "patient_status": {"type": "string", "enum": ["NEW", "RETURNING", "UNKNOWN"]},
        "body_part": {"type": ["string", "null"], "enum": sorted(BODY_PARTS.keys()) + [None]},
        "issue_type": {"type": ["string", "null"], "enum": sorted(ISSUE_TYPES) + [None]},
        "preferred_doctor_name": {"type": ["string", "null"]},
        "preferred_location_code": {"type": ["string", "null"]},
        "clarification_required": {"type": "boolean"},
        "clarification_question": {"type": ["string", "null"]},
        "caller_correction": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "properties": {
                "patient_status": {"type": ["string", "null"], "enum": ["NEW", "RETURNING", "UNKNOWN", None]},
                "body_part": {"type": ["string", "null"], "enum": sorted(BODY_PARTS.keys()) + [None]},
                "issue_type": {"type": ["string", "null"], "enum": sorted(ISSUE_TYPES) + [None]},
                "preferred_doctor_name": {"type": ["string", "null"]},
                "preferred_location_code": {"type": ["string", "null"]},
            },
            "required": sorted(CORRECTION_FIELDS),
        },
    },
    "required": sorted(INTENT_FIELDS),
}


def validate_intent_payload(
    payload: dict[str, Any],
    *,
    known_doctor_names: list[str],
    known_location_codes: set[str] | None = None,
) -> StructuredIntent:
    extra_fields = set(payload) - INTENT_FIELDS
    missing_fields = INTENT_FIELDS - set(payload)
    if extra_fields or missing_fields:
        raise OpenAIIntegrationError(
            "OPENAI_STRUCTURED_OUTPUT_INVALID",
            "Structured intent output did not match the required contract.",
        )

    raw_user_text = _required_string(payload["raw_user_text"], "raw_user_text")
    patient_status = _normalize_patient_status(payload["patient_status"], "patient_status")
    body_part = _normalize_nullable_body_part(payload["body_part"], "body_part")
    issue_type = _normalize_nullable_issue_type(payload["issue_type"], "issue_type")
    doctor_name = _resolve_doctor_name(payload["preferred_doctor_name"], known_doctor_names)
    location_code = _resolve_location_code(payload["preferred_location_code"], known_location_codes)
    clarification_required = payload["clarification_required"]
    if not isinstance(clarification_required, bool):
        raise OpenAIIntegrationError("OPENAI_STRUCTURED_OUTPUT_INVALID", "clarification_required must be boolean.")
    clarification_question = _nullable_string(payload["clarification_question"], "clarification_question")
    if clarification_required and not clarification_question:
        raise OpenAIIntegrationError(
            "OPENAI_STRUCTURED_OUTPUT_INVALID",
            "A clarification question is required when the intent is incomplete.",
        )
    _reject_unsafe_text(clarification_question or "")
    correction = _normalize_correction(payload["caller_correction"], known_doctor_names, known_location_codes)
    return StructuredIntent(
        raw_user_text=raw_user_text,
        patient_status=patient_status,
        body_part=body_part,
        issue_type=issue_type,
        preferred_doctor_name=doctor_name,
        preferred_location_code=location_code,
        clarification_required=clarification_required,
        clarification_question=clarification_question,
        caller_correction=correction,
    )


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OpenAIIntegrationError("OPENAI_STRUCTURED_OUTPUT_INVALID", f"{field} must be a non-empty string.")
    return value.strip()


def _nullable_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise OpenAIIntegrationError("OPENAI_STRUCTURED_OUTPUT_INVALID", f"{field} must be a string or null.")
    cleaned = value.strip()
    return cleaned or None


def _normalize_patient_status(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise OpenAIIntegrationError("OPENAI_STRUCTURED_OUTPUT_INVALID", f"{field} must be a string.")
    normalized = value.strip().upper()
    if normalized not in PATIENT_STATUSES:
        raise OpenAIIntegrationError("OPENAI_PATIENT_STATUS_INVALID", "Patient status was outside the allowed enum.")
    return normalized


def _normalize_nullable_body_part(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise OpenAIIntegrationError("OPENAI_STRUCTURED_OUTPUT_INVALID", f"{field} must be a string or null.")
    try:
        return normalize_body_part(value)
    except Exception as error:
        raise OpenAIIntegrationError(
            "OPENAI_BODY_PART_INVALID",
            "Body part was outside the scheduling protocol.",
        ) from error


def _normalize_nullable_issue_type(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise OpenAIIntegrationError("OPENAI_STRUCTURED_OUTPUT_INVALID", f"{field} must be a string or null.")
    try:
        return normalize_issue_type(value)
    except Exception as error:
        raise OpenAIIntegrationError(
            "OPENAI_ISSUE_TYPE_INVALID",
            "Issue type was outside the scheduling protocol.",
        ) from error


def _resolve_doctor_name(value: Any, known_doctor_names: list[str]) -> str | None:
    cleaned = _nullable_string(value, "preferred_doctor_name")
    if cleaned is None:
        return None
    candidates = {_doctor_key(name): name for name in known_doctor_names}
    candidates.update({_last_name_key(name): name for name in known_doctor_names})
    resolved = candidates.get(_doctor_key(cleaned)) or candidates.get(_last_name_key(cleaned))
    if resolved is None:
        raise OpenAIIntegrationError(
            "OPENAI_DOCTOR_NAME_INVALID",
            "Preferred physician name was not found in the deterministic physician roster.",
        )
    return resolved


def _resolve_location_code(value: Any, known_location_codes: set[str] | None) -> str | None:
    cleaned = _nullable_string(value, "preferred_location_code")
    if cleaned is None:
        return None
    allowed = known_location_codes or DEFAULT_LOCATION_CODES
    normalized = cleaned.upper()
    if normalized not in allowed:
        raise OpenAIIntegrationError(
            "OPENAI_LOCATION_CODE_INVALID",
            "Preferred location code was not found in the deterministic location roster.",
        )
    return normalized


def _normalize_correction(
    value: Any,
    known_doctor_names: list[str],
    known_location_codes: set[str] | None,
) -> dict[str, str | None]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise OpenAIIntegrationError("OPENAI_STRUCTURED_OUTPUT_INVALID", "caller_correction must be an object or null.")
    if set(value) - CORRECTION_FIELDS:
        raise OpenAIIntegrationError("OPENAI_STRUCTURED_OUTPUT_INVALID", "caller_correction has unsupported fields.")
    correction: dict[str, str | None] = {}
    if "patient_status" in value and value["patient_status"] not in (None, ""):
        correction["patient_status"] = _normalize_patient_status(
            value["patient_status"],
            "caller_correction.patient_status",
        )
    if "body_part" in value and value["body_part"] not in (None, ""):
        correction["body_part"] = _normalize_nullable_body_part(value["body_part"], "caller_correction.body_part")
    if "issue_type" in value and value["issue_type"] not in (None, ""):
        correction["issue_type"] = _normalize_nullable_issue_type(value["issue_type"], "caller_correction.issue_type")
    if "preferred_doctor_name" in value and value["preferred_doctor_name"] not in (None, ""):
        correction["preferred_doctor_name"] = _resolve_doctor_name(value["preferred_doctor_name"], known_doctor_names)
    if "preferred_location_code" in value and value["preferred_location_code"] not in (None, ""):
        correction["preferred_location_code"] = _resolve_location_code(
            value["preferred_location_code"],
            known_location_codes,
        )
    return correction


def _doctor_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace("dr.", "").strip())


def _last_name_key(value: str) -> str:
    return _doctor_key(value).split(" ")[-1]


def _reject_unsafe_text(value: str) -> None:
    cleaned = value.lower()
    blocked = (
        "diagnosis",
        "diagnose",
        "take medication",
        "prescribe",
        "treatment recommendation",
        "soap note",
        "icd",
        "billing code",
        "patient id",
        "physician id",
        "doctor id",
        "slot id",
        "call id",
        "database id",
        "your appointment is booked",
        "appointment is confirmed",
    )
    if any(phrase in cleaned for phrase in blocked):
        raise OpenAIIntegrationError(
            "OPENAI_BOUNDARY_VIOLATION",
            "Model output crossed the scheduling-only safety boundary.",
        )
