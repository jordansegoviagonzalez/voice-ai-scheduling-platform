from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Call, Organization, Slot
from app.services.organizations import resolve_active_organization_by_slug

DEFAULT_ORGANIZATION_SLUG = "default-orthopedics"
DEFAULT_ORGANIZATION_NAME = "Default Orthopedics"
DEFAULT_ORGANIZATION_TIMEZONE = "America/Los_Angeles"


def default_organization(session: Session) -> Organization:
    organization = session.scalar(select(Organization).where(Organization.slug == DEFAULT_ORGANIZATION_SLUG))
    if organization is not None:
        organization.name = DEFAULT_ORGANIZATION_NAME
        organization.status = "ACTIVE"
        organization.timezone = DEFAULT_ORGANIZATION_TIMEZONE
        return organization

    organization = Organization(
        slug=DEFAULT_ORGANIZATION_SLUG,
        name=DEFAULT_ORGANIZATION_NAME,
        status="ACTIVE",
        timezone=DEFAULT_ORGANIZATION_TIMEZONE,
    )
    session.add(organization)
    session.flush()
    return organization


def default_organization_id(session: Session) -> int:
    return default_organization(session).id


def explicit_organization_id_from_slug(session: Session, organization_slug: str) -> int:
    return resolve_active_organization_by_slug(session, organization_slug).id


def call_organization_id(
    session: Session,
    *,
    call_id: int | None,
    explicit_organization_id: int | None = None,
) -> int:
    if call_id is not None:
        call = session.get(Call, call_id)
        if call is not None:
            if explicit_organization_id is not None and call.organization_id != explicit_organization_id:
                raise ApiError(
                    "ORGANIZATION_CONTEXT_MISMATCH",
                    "The requested call does not belong to this organization.",
                    409,
                )
            return call.organization_id
    if explicit_organization_id is not None:
        return explicit_organization_id
    return default_organization_id(session)


def assert_call_matches_organization(session: Session, *, call_id: int, organization_id: int) -> None:
    call = session.get(Call, call_id)
    if call is None:
        raise ApiError("CALL_NOT_FOUND", "Call was not found.", 404)
    if call.organization_id != organization_id:
        raise ApiError(
            "ORGANIZATION_CONTEXT_MISMATCH",
            "The requested call does not belong to this organization.",
            409,
        )


def assert_slot_matches_organization(session: Session, *, slot_id: int, organization_id: int) -> None:
    slot_organization_id = session.scalar(select(Slot.organization_id).where(Slot.id == slot_id))
    if slot_organization_id is None:
        raise ApiError("SLOT_NOT_FOUND", "The selected appointment slot was not found.", 404)
    if slot_organization_id != organization_id:
        raise ApiError(
            "ORGANIZATION_CONTEXT_MISMATCH",
            "The selected slot does not belong to this organization.",
            409,
        )
