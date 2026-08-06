from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organization

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
