from __future__ import annotations

import re

from werkzeug.security import check_password_hash, generate_password_hash

from app.errors import ApiError

NEW_ACCOUNT_PASSWORD_MIN_LENGTH = 12
NEW_ACCOUNT_PASSWORD_MAX_LENGTH = 128
GENERIC_PATIENT_LOGIN_FAILURE = "We could not verify those patient details."


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ApiError("VALIDATION_ERROR", "Enter a valid email address.", 422, {"email": ["Invalid email"]})
    return email


def validate_new_account_password(password: object, confirmation: object) -> str:
    field_errors: dict[str, list[str]] = {}
    if not isinstance(password, str):
        field_errors["password"] = ["This field is required"]
    if not isinstance(confirmation, str):
        field_errors["confirmPassword"] = ["This field is required"]
    if field_errors:
        raise ApiError("VALIDATION_ERROR", "Required fields are missing.", 422, field_errors)

    assert isinstance(password, str)
    assert isinstance(confirmation, str)
    if password != confirmation:
        raise ApiError(
            "VALIDATION_ERROR",
            "Passwords do not match.",
            422,
            {"confirmPassword": ["Passwords do not match"]},
        )
    password_errors = _password_policy_errors(password)
    if password_errors:
        raise ApiError("VALIDATION_ERROR", "Password does not meet the account policy.", 422, password_errors)
    return password


def hash_patient_password(password: str) -> str:
    return generate_password_hash(password)


def verify_patient_password(stored_hash: str | None, password: object) -> bool:
    if not stored_hash or not isinstance(password, str):
        return False
    return check_password_hash(stored_hash, password)


def patient_login_error() -> ApiError:
    return ApiError("UNAUTHORIZED", GENERIC_PATIENT_LOGIN_FAILURE, 401)


def _password_policy_errors(password: str) -> dict[str, list[str]]:
    errors: list[str] = []
    if not password or not password.strip():
        errors.append("Password is required")
    if len(password) < NEW_ACCOUNT_PASSWORD_MIN_LENGTH:
        errors.append(f"Use at least {NEW_ACCOUNT_PASSWORD_MIN_LENGTH} characters")
    if len(password) > NEW_ACCOUNT_PASSWORD_MAX_LENGTH:
        errors.append(f"Use no more than {NEW_ACCOUNT_PASSWORD_MAX_LENGTH} characters")
    return {"password": errors} if errors else {}
