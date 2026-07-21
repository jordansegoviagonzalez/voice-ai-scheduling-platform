from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.domain.routing import PhysicianRoutingService, RoutingRequest
from app.extensions import get_session
from app.routes.common import int_or_none, json_body, parse_datetime, require_fields

bp = Blueprint("routing", __name__)


@bp.post("/routing/recommendations")
def routing_recommendations():  # type: ignore[no-untyped-def]
    payload = json_body(request)
    require_fields(payload, "patient_status", "body_part", "issue_type")
    session = get_session()
    result = PhysicianRoutingService(session).recommend(
        RoutingRequest(
            patient_id=int_or_none(payload.get("patient_id"), "patient_id"),
            patient_status=str(payload["patient_status"]),
            body_part=str(payload["body_part"]),
            issue_type=str(payload["issue_type"]),
            preferred_doctor_id=int_or_none(payload.get("preferred_doctor_id"), "preferred_doctor_id"),
            preferred_location_id=int_or_none(payload.get("preferred_location_id"), "preferred_location_id"),
            call_id=int_or_none(payload.get("call_id"), "call_id"),
            starts_after=parse_datetime(payload.get("starts_after"), "starts_after"),
            ends_before=parse_datetime(payload.get("ends_before"), "ends_before"),
        ),
        persist=bool(payload.get("call_id")),
    )
    session.commit()
    return jsonify(result)
