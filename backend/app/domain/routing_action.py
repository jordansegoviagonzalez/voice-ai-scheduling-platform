from enum import Enum
from typing import Any

class RoutingAction(str, Enum):
    BOOK = "book"
    CLARIFY = "clarify"
    REJECT = "reject"
    ESCALATE = "escalate"
    ROUTE_ADMIN = "route_admin"

from app.observability.langsmith_tracing import safe_traceable

@safe_traceable(name="Routing Action")
def compute_routing_action(
    *,
    chat_status: str | None = None,
    escalation_type: str | None = None,
    routing_result: dict[str, Any] | None = None,
    is_clarifying: bool = False,
) -> RoutingAction:
    if escalation_type == "emergency":
        return RoutingAction.ESCALATE

    if escalation_type == "care_team_handoff":
        if routing_result:
            rejected = routing_result.get("rejected_doctors", [])
            exceptions = routing_result.get("availability_exceptions", [])
            if (rejected or exceptions) and not routing_result.get("web_recommendations") and not routing_result.get("ranked_recommendations"):
                return RoutingAction.REJECT
        return RoutingAction.ROUTE_ADMIN

    if routing_result and "normalized_request" in routing_result:
        issue_type = routing_result["normalized_request"].get("issue_type")
        if issue_type in {"Medication/Refill", "Lab/Test Result", "Administrative", "Referral", "Paperwork"}:
            return RoutingAction.ROUTE_ADMIN

    if chat_status in {"CONFIRMED", "SELECTING_APPOINTMENT"}:
        return RoutingAction.BOOK

    if chat_status in {"COLLECTING_INTAKE", "clarification_required"} or is_clarifying:
        return RoutingAction.CLARIFY

    if routing_result:
        # Check if we have recommendations -> BOOK
        if routing_result.get("web_recommendations") or routing_result.get("recommended") or routing_result.get("ranked_recommendations"):
            return RoutingAction.BOOK
        # Otherwise, if we have rejected doctors or availability exceptions -> REJECT
        if routing_result.get("rejected_doctors") or routing_result.get("availability_exceptions"):
            return RoutingAction.REJECT

    return RoutingAction.CLARIFY
