from __future__ import annotations

import re
import unicodedata
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.domain.normalization import normalize_body_part, normalize_issue_type
from app.errors import ApiError
from app.models import Doctor, DoctorCapability, Location, Organization

ACTIVE_ORGANIZATION_STATUS = "ACTIVE"
INACTIVE_ORGANIZATION_STATUS = "INACTIVE"
VALID_ORGANIZATION_STATUSES = {ACTIVE_ORGANIZATION_STATUS, INACTIVE_ORGANIZATION_STATUS}
DEFAULT_ORGANIZATION_TIMEZONE = "America/Los_Angeles"
SLUG_MAX_LENGTH = 80


def normalize_organization_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:SLUG_MAX_LENGTH].strip("-")


def organization_or_404(session: Session, organization_id: int) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise ApiError("ORGANIZATION_NOT_FOUND", "Organization was not found.", 404)
    return organization


def resolve_active_organization_by_slug(session: Session, slug: str) -> Organization:
    normalized_slug = normalize_organization_slug(slug)
    if not normalized_slug:
        raise ApiError("ORGANIZATION_NOT_FOUND", "Organization was not found.", 404)
    organization = session.scalar(select(Organization).where(Organization.slug == normalized_slug))
    if organization is None:
        raise ApiError("ORGANIZATION_NOT_FOUND", "Organization was not found.", 404)
    if organization.status != ACTIVE_ORGANIZATION_STATUS:
        raise ApiError("ORGANIZATION_INACTIVE", "This organization is not active.", 409)
    return organization


def create_organization(session: Session, payload: dict[str, Any]) -> Organization:
    name = _string_field(payload, "name", max_length=160)
    raw_slug = _string_field(payload, "slug", max_length=160, required=False)
    slug = normalize_organization_slug(raw_slug or name)
    if not slug:
        raise ApiError(
            "VALIDATION_ERROR",
            "Organization slug could not be generated.",
            422,
            {"slug": ["Invalid slug"]},
        )
    status = _organization_status(payload.get("status", ACTIVE_ORGANIZATION_STATUS))
    timezone = _timezone(payload.get("timezone", DEFAULT_ORGANIZATION_TIMEZONE))
    business_hours = payload.get("business_hours", {})
    if not isinstance(business_hours, dict):
        raise ApiError("VALIDATION_ERROR", "business_hours must be an object.", 422, {"business_hours": ["Invalid object"]})
    voice_enabled = _bool_field(payload, "voice_enabled", required=False, default=False)
    voice_phone_number = _string_field(payload, "voice_phone_number", max_length=20, required=False) if payload.get("voice_phone_number") is not None else None

    _ensure_slug_available(session, slug)

    organization = Organization(
        slug=slug,
        name=name,
        status=status,
        timezone=timezone,
        business_hours=business_hours,
        voice_enabled=voice_enabled,
        voice_phone_number=voice_phone_number,
    )
    session.add(organization)
    _flush_or_slug_conflict(session)
    return organization


def update_organization(session: Session, organization: Organization, payload: dict[str, Any]) -> Organization:
    if "name" in payload:
        organization.name = _string_field(payload, "name", max_length=160)
    if "slug" in payload:
        slug = normalize_organization_slug(_string_field(payload, "slug", max_length=160))
        if not slug:
            raise ApiError(
                "VALIDATION_ERROR",
                "Organization slug could not be generated.",
                422,
                {"slug": ["Invalid slug"]},
            )
        if slug != organization.slug:
            _ensure_slug_available(session, slug, exclude_organization_id=organization.id)
            organization.slug = slug
    if "status" in payload:
        organization.status = _organization_status(payload["status"])
    if "timezone" in payload:
        organization.timezone = _timezone(payload["timezone"])
    if "business_hours" in payload:
        business_hours = payload["business_hours"]
        if not isinstance(business_hours, dict):
            raise ApiError("VALIDATION_ERROR", "business_hours must be an object.", 422, {"business_hours": ["Invalid object"]})
        organization.business_hours = business_hours
    if "voice_enabled" in payload:
        organization.voice_enabled = _bool_field(payload, "voice_enabled", required=True)
    if "voice_phone_number" in payload:
        val = payload["voice_phone_number"]
        if val is None:
            organization.voice_phone_number = None
        else:
            organization.voice_phone_number = _string_field(payload, "voice_phone_number", max_length=20)

    _flush_or_slug_conflict(session)
    return organization


def doctor_or_404(session: Session, organization_id: int, doctor_id: int) -> Doctor:
    doctor = session.scalar(_doctor_query(organization_id).where(Doctor.id == doctor_id))
    if doctor is None:
        raise ApiError("DOCTOR_NOT_FOUND", "Physician was not found for this organization.", 404)
    return doctor


def doctor_query(organization_id: int):  # type: ignore[no-untyped-def]
    return _doctor_query(organization_id)


def create_doctor(session: Session, organization: Organization, payload: dict[str, Any]) -> Doctor:
    first_name = _string_field(payload, "first_name", max_length=100)
    last_name = _string_field(payload, "last_name", max_length=100)
    accepts_new_patients = _bool_field(payload, "accepts_new_patients", required=True)
    active = _bool_field(payload, "active", required=False, default=True)
    _ensure_doctor_name_available(session, organization.id, first_name, last_name)

    doctor = Doctor(
        organization_id=organization.id,
        first_name=first_name,
        last_name=last_name,
        accepts_new_patients=accepts_new_patients,
        active=active,
    )
    session.add(doctor)
    doctor.locations = _locations_for_payload(session, organization.id, payload)
    capabilities = _capabilities_for_payload(payload)
    if capabilities is not None:
        doctor.capabilities = [
            DoctorCapability(body_part=body_part, issue_type=issue_type) for body_part, issue_type in capabilities
        ]
    _flush_or_doctor_conflict(session)
    return doctor


def update_doctor(session: Session, organization: Organization, doctor: Doctor, payload: dict[str, Any]) -> Doctor:
    first_name = _string_field(payload, "first_name", max_length=100) if "first_name" in payload else doctor.first_name
    last_name = _string_field(payload, "last_name", max_length=100) if "last_name" in payload else doctor.last_name
    if first_name != doctor.first_name or last_name != doctor.last_name:
        _ensure_doctor_name_available(session, organization.id, first_name, last_name, exclude_doctor_id=doctor.id)
        doctor.first_name = first_name
        doctor.last_name = last_name

    if "accepts_new_patients" in payload:
        doctor.accepts_new_patients = _bool_field(payload, "accepts_new_patients", required=True)
    if "active" in payload:
        doctor.active = _bool_field(payload, "active", required=True)
    if "location_ids" in payload:
        doctor.locations = _locations_for_payload(session, organization.id, payload)
    capabilities = _capabilities_for_payload(payload)
    if capabilities is not None:
        doctor.capabilities = [
            DoctorCapability(body_part=body_part, issue_type=issue_type) for body_part, issue_type in capabilities
        ]

    _flush_or_doctor_conflict(session)
    return doctor


def _doctor_query(organization_id: int):  # type: ignore[no-untyped-def]
    return (
        select(Doctor)
        .where(Doctor.organization_id == organization_id)
        .options(selectinload(Doctor.locations), selectinload(Doctor.capabilities))
        .order_by(Doctor.last_name, Doctor.first_name)
    )


def _string_field(payload: dict[str, Any], field: str, *, max_length: int, required: bool = True) -> str:
    value = payload.get(field)
    if value in (None, ""):
        if required:
            raise ApiError(
                "VALIDATION_ERROR",
                "Required fields are missing.",
                422,
                {field: ["This field is required"]},
            )
        return ""
    if not isinstance(value, str):
        raise ApiError("VALIDATION_ERROR", f"{field} must be a string.", 422, {field: ["Invalid string"]})
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
    return cleaned


def _bool_field(
    payload: dict[str, Any],
    field: str,
    *,
    required: bool,
    default: bool | None = None,
) -> bool:
    value = payload.get(field)
    if value is None:
        if required:
            raise ApiError(
                "VALIDATION_ERROR",
                "Required fields are missing.",
                422,
                {field: ["This field is required"]},
            )
        if default is None:
            raise ApiError("VALIDATION_ERROR", f"{field} must be true or false.", 422, {field: ["Invalid boolean"]})
        return default
    if not isinstance(value, bool):
        raise ApiError("VALIDATION_ERROR", f"{field} must be true or false.", 422, {field: ["Invalid boolean"]})
    return value


def _organization_status(value: Any) -> str:
    if not isinstance(value, str):
        raise ApiError("VALIDATION_ERROR", "status must be a string.", 422, {"status": ["Invalid status"]})
    status = value.strip().upper()
    if status not in VALID_ORGANIZATION_STATUSES:
        raise ApiError(
            "VALIDATION_ERROR",
            "status must be ACTIVE or INACTIVE.",
            422,
            {"status": ["Invalid status"]},
        )
    return status


def _timezone(value: Any) -> str:
    if not isinstance(value, str):
        raise ApiError("VALIDATION_ERROR", "timezone must be a string.", 422, {"timezone": ["Invalid timezone"]})
    timezone = value.strip()
    if not timezone:
        raise ApiError("VALIDATION_ERROR", "timezone is required.", 422, {"timezone": ["This field is required"]})
    if len(timezone) > 64:
        raise ApiError(
            "FIELD_TOO_LONG",
            "timezone exceeds the maximum length.",
            413,
            {"timezone": ["Maximum length is 64 characters"]},
        )
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ApiError(
            "VALIDATION_ERROR",
            "timezone must be a valid IANA timezone.",
            422,
            {"timezone": ["Invalid timezone"]},
        ) from error
    return timezone


def _ensure_slug_available(
    session: Session,
    slug: str,
    *,
    exclude_organization_id: int | None = None,
) -> None:
    statement = select(Organization.id).where(Organization.slug == slug)
    if exclude_organization_id is not None:
        statement = statement.where(Organization.id != exclude_organization_id)
    if session.scalar(statement) is not None:
        raise ApiError("ORGANIZATION_SLUG_CONFLICT", "Organization slug is already in use.", 409)


def _ensure_doctor_name_available(
    session: Session,
    organization_id: int,
    first_name: str,
    last_name: str,
    *,
    exclude_doctor_id: int | None = None,
) -> None:
    statement = select(Doctor.id).where(
        Doctor.organization_id == organization_id,
        Doctor.first_name == first_name,
        Doctor.last_name == last_name,
    )
    if exclude_doctor_id is not None:
        statement = statement.where(Doctor.id != exclude_doctor_id)
    if session.scalar(statement) is not None:
        raise ApiError("DOCTOR_CONFLICT", "A physician with this name already exists for this organization.", 409)


def _location_ids(payload: dict[str, Any]) -> list[int]:
    raw_ids = payload.get("location_ids")
    if raw_ids is None:
        return []
    if not isinstance(raw_ids, list):
        raise ApiError("VALIDATION_ERROR", "location_ids must be a list.", 422, {"location_ids": ["Invalid list"]})
    ids: list[int] = []
    for index, raw_id in enumerate(raw_ids):
        if not isinstance(raw_id, int) or isinstance(raw_id, bool):
            raise ApiError(
                "VALIDATION_ERROR",
                "location_ids must contain integers.",
                422,
                {f"location_ids[{index}]": ["Invalid integer"]},
            )
        ids.append(raw_id)
    return list(dict.fromkeys(ids))


def _locations_for_payload(session: Session, organization_id: int, payload: dict[str, Any]) -> list[Location]:
    ids = _location_ids(payload)
    if not ids:
        return []
    locations = list(
        session.scalars(select(Location).where(Location.organization_id == organization_id, Location.id.in_(ids)))
    )
    location_by_id = {location.id: location for location in locations}
    if set(location_by_id) != set(ids):
        raise ApiError(
            "LOCATION_NOT_FOUND",
            "One or more locations were not found for this organization.",
            404,
        )
    return [location_by_id[location_id] for location_id in ids]


def _capabilities_for_payload(payload: dict[str, Any]) -> list[tuple[str, str]] | None:
    if "capabilities" not in payload:
        return None
    raw_capabilities = payload.get("capabilities")
    if raw_capabilities is None:
        return []
    if not isinstance(raw_capabilities, list):
        raise ApiError("VALIDATION_ERROR", "capabilities must be a list.", 422, {"capabilities": ["Invalid list"]})

    capabilities: list[tuple[str, str]] = []
    for index, raw_capability in enumerate(raw_capabilities):
        if not isinstance(raw_capability, dict):
            raise ApiError(
                "VALIDATION_ERROR",
                "Each capability must be an object.",
                422,
                {f"capabilities[{index}]": ["Invalid object"]},
            )
        if raw_capability.get("body_part") in (None, "") or raw_capability.get("issue_type") in (None, ""):
            raise ApiError(
                "VALIDATION_ERROR",
                "Each capability requires body_part and issue_type.",
                422,
                {
                    f"capabilities[{index}].body_part": ["This field is required"],
                    f"capabilities[{index}].issue_type": ["This field is required"],
                },
            )
        body_part = normalize_body_part(str(raw_capability["body_part"]))
        issue_type = normalize_issue_type(str(raw_capability["issue_type"]))
        capability = (body_part, issue_type)
        if capability not in capabilities:
            capabilities.append(capability)
    return capabilities


def _flush_or_slug_conflict(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise ApiError("ORGANIZATION_SLUG_CONFLICT", "Organization slug is already in use.", 409) from error


def _flush_or_doctor_conflict(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise ApiError(
            "DOCTOR_CONFLICT",
            "A physician with this name already exists for this organization.",
            409,
        ) from error

def location_or_404(session: Session, organization_id: int, location_id: int) -> Location:
    location = session.scalar(_location_query(organization_id).where(Location.id == location_id))
    if location is None:
        raise ApiError("LOCATION_NOT_FOUND", "Location was not found for this organization.", 404)
    return location

def location_query(organization_id: int):  # type: ignore[no-untyped-def]
    return _location_query(organization_id)

def _location_query(organization_id: int):  # type: ignore[no-untyped-def]
    return (
        select(Location)
        .where(Location.organization_id == organization_id)
        .order_by(Location.name)
    )

def create_location(session: Session, organization: Organization, payload: dict[str, Any]) -> Location:
    code = _string_field(payload, "code", max_length=16)
    name = _string_field(payload, "name", max_length=120)

    location = Location(
        organization_id=organization.id,
        code=code,
        name=name,
        address_line1=payload.get("address_line1"),
        address_line2=payload.get("address_line2"),
        city=payload.get("city"),
        state=payload.get("state"),
        postal_code=payload.get("postal_code"),
    )
    session.add(location)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise ApiError("LOCATION_CONFLICT", "A location with this code or name already exists.", 409) from error
    return location

def update_location(session: Session, organization: Organization, location: Location, payload: dict[str, Any]) -> Location:
    if "code" in payload:
        location.code = _string_field(payload, "code", max_length=16)
    if "name" in payload:
        location.name = _string_field(payload, "name", max_length=120)
    if "address_line1" in payload:
        location.address_line1 = payload.get("address_line1")
    if "address_line2" in payload:
        location.address_line2 = payload.get("address_line2")
    if "city" in payload:
        location.city = payload.get("city")
    if "state" in payload:
        location.state = payload.get("state")
    if "postal_code" in payload:
        location.postal_code = payload.get("postal_code")

    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise ApiError("LOCATION_CONFLICT", "A location with this code or name already exists.", 409) from error
    return location
