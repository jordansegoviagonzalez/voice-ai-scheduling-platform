from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from flask import Request, current_app

from app.errors import ApiError


def json_body(request: Request) -> dict[str, Any]:
    max_length = current_app.config.get("MAX_CONTENT_LENGTH")
    if max_length and request.content_length and request.content_length > int(max_length):
        raise ApiError(
            "REQUEST_ENTITY_TOO_LARGE",
            "The request body is too large.",
            413,
        )
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError("INVALID_JSON", "A JSON object is required.", 400)
    _reject_unbounded_json_strings(payload)
    return payload


def require_fields(payload: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if payload.get(field) in (None, "")]
    if missing:
        raise ApiError(
            "VALIDATION_ERROR",
            "Required fields are missing.",
            422,
            {field: ["This field is required"] for field in missing},
        )


def parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ApiError(
            "VALIDATION_ERROR",
            f"{field} must use YYYY-MM-DD format.",
            422,
            {field: ["Invalid date"]},
        ) from error


def parse_datetime(value: str | None, field: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ApiError(
            "VALIDATION_ERROR",
            f"{field} must be an ISO-8601 datetime.",
            422,
            {field: ["Invalid datetime"]},
        ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def int_or_none(value: Any, field: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ApiError(
            "VALIDATION_ERROR",
            f"{field} must be an integer.",
            422,
            {field: ["Invalid integer"]},
        ) from error


def bounded_string(
    payload: dict[str, Any],
    field: str,
    *,
    max_length: int,
    required: bool = True,
) -> str | None:
    value = payload.get(field)
    if value in (None, ""):
        if required:
            raise ApiError(
                "VALIDATION_ERROR",
                "Required fields are missing.",
                422,
                {field: ["This field is required"]},
            )
        return None
    if not isinstance(value, str):
        raise ApiError(
            "VALIDATION_ERROR",
            f"{field} must be a string.",
            422,
            {field: ["Invalid string"]},
        )
    cleaned = value.strip()
    if required and not cleaned:
        raise ApiError(
            "VALIDATION_ERROR",
            "Required fields are missing.",
            422,
            {field: ["This field is required"]},
        )
    if len(cleaned) > max_length:
        raise ApiError(
            "FIELD_TOO_LONG",
            f"{field} exceeds the maximum length.",
            413,
            {field: [f"Maximum length is {max_length} characters"]},
        )
    return cleaned or None


def _reject_unbounded_json_strings(value: Any) -> None:
    max_length = int(current_app.config.get("JSON_STRING_FIELD_MAX_LENGTH", 8192))
    if max_length <= 0:
        return
    stack = [("", value)]
    while stack:
        path, current = stack.pop()
        if isinstance(current, dict):
            stack.extend((f"{path}.{key}" if path else str(key), child) for key, child in current.items())
        elif isinstance(current, list):
            stack.extend((f"{path}[{index}]", child) for index, child in enumerate(current))
        elif isinstance(current, str) and len(current) > max_length:
            field = path or "payload"
            raise ApiError(
                "FIELD_TOO_LONG",
                f"{field} exceeds the maximum length.",
                413,
                {field: [f"Maximum length is {max_length} characters"]},
            )
