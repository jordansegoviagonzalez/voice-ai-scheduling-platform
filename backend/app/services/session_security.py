from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import current_app
from flask import session as browser_session

from app.errors import ApiError

PATIENT_KEYS = ("patient_authenticated", "patient_id", "patient_chat_session_ids", "patient_last_activity_at")
ADMIN_KEYS = (
    "admin_authenticated",
    "admin_name",
    "admin_email",
    "admin_role",
    "admin_last_activity_at",
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def start_patient_session(patient_id: int) -> None:
    browser_session["patient_authenticated"] = True
    browser_session["patient_id"] = patient_id
    touch_patient_session()


def remember_patient_chat_session(session_id: int) -> None:
    ids = set(browser_session.get("patient_chat_session_ids", []))
    ids.add(session_id)
    browser_session["patient_chat_session_ids"] = sorted(ids)


def remembered_patient_chat_session_ids() -> list[int]:
    raw_ids = browser_session.get("patient_chat_session_ids", [])
    if not isinstance(raw_ids, list):
        return []
    return [session_id for session_id in raw_ids if isinstance(session_id, int)]


def require_patient_session(*, refresh: bool = True) -> int:
    if not browser_session.get("patient_authenticated"):
        raise ApiError("UNAUTHORIZED", "Valid patient session required", 401)
    patient_id = browser_session.get("patient_id")
    if not isinstance(patient_id, int):
        clear_patient_session()
        raise ApiError("UNAUTHORIZED", "Invalid patient session identity", 401)
    _validate_idle_timeout("patient")
    if refresh:
        touch_patient_session()
    return patient_id


def has_patient_session() -> bool:
    return bool(browser_session.get("patient_authenticated"))


def touch_patient_session() -> None:
    browser_session["patient_last_activity_at"] = utcnow().isoformat()


def clear_patient_session() -> None:
    for key in PATIENT_KEYS:
        browser_session.pop(key, None)


def start_admin_session(*, name: str, email: str, role: str) -> None:
    browser_session["admin_authenticated"] = True
    browser_session["admin_name"] = name
    browser_session["admin_email"] = email
    browser_session["admin_role"] = role
    touch_admin_session()


def require_admin_session() -> None:
    if not browser_session.get("admin_authenticated"):
        raise ApiError("UNAUTHORIZED", "Valid admin session required", 401)
    if browser_session.get("admin_role") != "admin_provider":
        raise ApiError("FORBIDDEN", "Insufficient permissions", 403)
    if browser_session.get("admin_email") != current_app.config.get("ADMIN_EMAIL"):
        clear_admin_session()
        raise ApiError("UNAUTHORIZED", "Invalid admin session identity", 401)
    _validate_idle_timeout("admin")
    touch_admin_session()


def touch_admin_session() -> None:
    browser_session["admin_last_activity_at"] = utcnow().isoformat()


def clear_admin_session() -> None:
    for key in ADMIN_KEYS:
        browser_session.pop(key, None)


def _validate_idle_timeout(role: str) -> None:
    key = f"{role}_last_activity_at"
    raw_value = browser_session.get(key)
    if not raw_value:
        browser_session[key] = utcnow().isoformat()
        return
    try:
        last_activity = datetime.fromisoformat(str(raw_value))
    except ValueError as error:
        _clear_role(role)
        raise ApiError("SESSION_EXPIRED", "Your session expired because of inactivity.", 401) from error
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=UTC)
    timeout = timedelta(minutes=int(current_app.config.get("SESSION_IDLE_TIMEOUT_MINUTES", 60)))
    if utcnow() - last_activity > timeout:
        _clear_role(role)
        raise ApiError("SESSION_EXPIRED", "Your session expired because of inactivity.", 401)


def _clear_role(role: str) -> None:
    if role == "patient":
        clear_patient_session()
    elif role == "admin":
        clear_admin_session()
