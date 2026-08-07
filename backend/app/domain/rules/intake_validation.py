import re
from datetime import date
from typing import Any

from app.domain.normalization import normalize_body_part, normalize_date_of_birth, normalize_issue_type, normalize_phone

APPOINTMENT_TYPES = {"new_patient", "follow_up", "post_op", "urgent"}
SIDES = {"left", "right", "bilateral", "not_applicable"}
LOCATIONS = {"MAIN", "EAST", "NORTH", "WEST", "SOUTH", "ANY"}
TIME_OF_DAY_VALUES = {"morning", "afternoon", "any"}


def validate_intake_fields(fields: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    cleaned: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for field, value in fields.items():
        if value in (None, ""):
            continue
        cleaned[field] = value

    if "date_of_birth" in cleaned:
        try:
            dob = normalize_date_of_birth(str(cleaned["date_of_birth"]))
            if dob >= date.today():
                errors["date_of_birth"] = "Date of birth must be in the past."
            else:
                cleaned["date_of_birth"] = dob.isoformat()
        except Exception:
            errors["date_of_birth"] = "Enter a valid date of birth."

    if "phone" in cleaned:
        try:
            cleaned["phone"] = normalize_phone(str(cleaned["phone"]))
        except Exception:
            errors["phone"] = "Enter a valid phone number."

    if "body_part" in cleaned:
        try:
            cleaned["body_part"] = normalize_body_part(str(cleaned["body_part"]))
        except Exception:
            errors["body_part"] = "Choose a supported capability area for this organization."

    if "issue_type" in cleaned:
        try:
            cleaned["issue_type"] = normalize_issue_type(str(cleaned["issue_type"]))
        except Exception:
            errors["issue_type"] = "Clarify the visit reason or issue type."

    if "severity" in fields:
        try:
            severity = int(fields["severity"])
            if severity < 1 or severity > 10:
                errors["severity"] = "Severity must be between 1 and 10."
            else:
                cleaned["severity"] = severity
        except (TypeError, ValueError):
            errors["severity"] = "Severity must be a number from 1 to 10."

    if "appointment_type" in cleaned and cleaned["appointment_type"] not in APPOINTMENT_TYPES:
        errors["appointment_type"] = "Appointment type must be new patient, follow-up, post-op, or urgent."

    if "side" in cleaned and cleaned["side"] not in SIDES:
        errors["side"] = "Side must be left, right, bilateral, or not applicable."

    if "preferred_location" in cleaned:
        location = str(cleaned["preferred_location"]).strip().upper()
        if location not in LOCATIONS:
            errors["preferred_location"] = (
                "Location must be Main, East, North, West, South, or earliest available at any location."
            )
        else:
            cleaned["preferred_location"] = location

    if "preferred_time_of_day" in cleaned:
        time_preference = _normalize_time_of_day(str(cleaned["preferred_time_of_day"]))
        if time_preference not in TIME_OF_DAY_VALUES:
            errors["preferred_time_of_day"] = "Time preference must be morning, afternoon, or any time."
        else:
            cleaned["preferred_time_of_day"] = time_preference

    for field in errors:
        cleaned.pop(field, None)

    return cleaned, errors


def _normalize_time_of_day(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", value.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if re.search(r"\bmornings?\b", cleaned):
        return "morning"
    if re.search(r"\bafternoons?\b", cleaned):
        return "afternoon"
    if re.search(r"\bany\s*(time|appointment)?\b", cleaned) or re.search(r"\banytime\b", cleaned):
        return "any"
    return cleaned
