from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app.extensions import get_session
from app.models import Organization
from app.routes.auth import require_admin_session
from app.routes.common import json_body
from app.services.organizations import (
    create_doctor,
    create_organization,
    doctor_or_404,
    doctor_query,
    organization_or_404,
    resolve_active_organization_by_slug,
    update_doctor,
    update_organization,
)
from app.services.serializers import doctor_json, organization_json, public_organization_json

bp = Blueprint("organizations", __name__)


@bp.get("/organizations")
def list_organizations():  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    organizations = list(session.scalars(select(Organization).order_by(Organization.name, Organization.id)))
    return jsonify({"organizations": [organization_json(organization) for organization in organizations]})


@bp.post("/organizations")
def create_organization_endpoint():  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    organization = create_organization(session, json_body(request))
    session.commit()
    return jsonify({"organization": organization_json(organization)}), 201


@bp.get("/organizations/slug/<organization_slug>")
def resolve_organization_slug(organization_slug: str):  # type: ignore[no-untyped-def]
    session = get_session()
    organization = resolve_active_organization_by_slug(session, organization_slug)
    return jsonify({"organization": public_organization_json(organization)})


@bp.get("/organizations/<int:organization_id>")
def get_organization(organization_id: int):  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    organization = organization_or_404(session, organization_id)
    return jsonify({"organization": organization_json(organization)})


@bp.patch("/organizations/<int:organization_id>")
def patch_organization(organization_id: int):  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    organization = organization_or_404(session, organization_id)
    organization = update_organization(session, organization, json_body(request))
    session.commit()
    return jsonify({"organization": organization_json(organization)})


@bp.get("/organizations/<int:organization_id>/doctors")
def list_organization_doctors(organization_id: int):  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    organization_or_404(session, organization_id)
    doctors = list(session.scalars(doctor_query(organization_id)))
    return jsonify({"doctors": [doctor_json(doctor) for doctor in doctors]})


@bp.post("/organizations/<int:organization_id>/doctors")
def create_organization_doctor(organization_id: int):  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    organization = organization_or_404(session, organization_id)
    doctor = create_doctor(session, organization, json_body(request))
    session.commit()
    return jsonify({"doctor": doctor_json(doctor)}), 201


@bp.get("/organizations/<int:organization_id>/doctors/<int:doctor_id>")
def get_organization_doctor(organization_id: int, doctor_id: int):  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    organization_or_404(session, organization_id)
    doctor = doctor_or_404(session, organization_id, doctor_id)
    return jsonify({"doctor": doctor_json(doctor)})


@bp.patch("/organizations/<int:organization_id>/doctors/<int:doctor_id>")
def patch_organization_doctor(organization_id: int, doctor_id: int):  # type: ignore[no-untyped-def]
    require_admin_session()
    session = get_session()
    organization = organization_or_404(session, organization_id)
    doctor = doctor_or_404(session, organization_id, doctor_id)
    doctor = update_doctor(session, organization, doctor, json_body(request))
    session.commit()
    return jsonify({"doctor": doctor_json(doctor)})
