from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.domain.routing import PhysicianRoutingService, RoutingRequest
from app.extensions import get_session
from app.routes.common import int_or_none, json_body, parse_datetime, require_fields
from app.services.organization_context import (
    assert_call_matches_organization,
    default_organization_id,
    explicit_organization_id_from_slug,
)

bp = Blueprint("routing", __name__)


@bp.post("/routing/recommendations")
def routing_recommendations():  # type: ignore[no-untyped-def]
    session = get_session()
    return _routing_recommendations(default_organization_id(session), explicit_context=False)


@bp.post("/organizations/slug/<organization_slug>/routing/recommendations")
def organization_routing_recommendations(organization_slug: str):  # type: ignore[no-untyped-def]
    session = get_session()
    return _routing_recommendations(
        explicit_organization_id_from_slug(session, organization_slug),
        explicit_context=True,
    )


def _routing_recommendations(organization_id: int, *, explicit_context: bool):  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(payload, "patient_status", "body_part", "issue_type")
    session = get_session()
    call_id = int_or_none(payload.get("call_id"), "call_id")
    if explicit_context and call_id is not None:
        assert_call_matches_organization(session, call_id=call_id, organization_id=organization_id)
    result = PhysicianRoutingService(session).recommend(
        RoutingRequest(
            organization_id=organization_id,
            patient_id=int_or_none(payload.get("patient_id"), "patient_id"),
            patient_status=str(payload["patient_status"]),
            body_part=str(payload["body_part"]),
            issue_type=str(payload["issue_type"]),
            preferred_doctor_id=int_or_none(payload.get("preferred_doctor_id"), "preferred_doctor_id"),
            preferred_location_id=int_or_none(payload.get("preferred_location_id"), "preferred_location_id"),
            call_id=call_id,
            starts_after=parse_datetime(payload.get("starts_after"), "starts_after"),
            ends_before=parse_datetime(payload.get("ends_before"), "ends_before"),
        ),
        persist=bool(payload.get("call_id")),
    )
    session.commit()
    return jsonify(result)
