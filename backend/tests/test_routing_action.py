import pytest
from app.domain.routing_action import RoutingAction, compute_routing_action

def test_book_action():
    assert compute_routing_action(chat_status="CONFIRMED") == RoutingAction.BOOK
    assert compute_routing_action(chat_status="SELECTING_APPOINTMENT") == RoutingAction.BOOK
    assert compute_routing_action(
        chat_status="ROUTING",
        routing_result={"web_recommendations": [{"dummy": "slot"}]}
    ) == RoutingAction.BOOK

def test_clarify_action():
    assert compute_routing_action(chat_status="COLLECTING_INTAKE") == RoutingAction.CLARIFY
    assert compute_routing_action(chat_status="clarification_required") == RoutingAction.CLARIFY
    assert compute_routing_action(is_clarifying=True) == RoutingAction.CLARIFY

def test_escalate_action():
    assert compute_routing_action(escalation_type="emergency") == RoutingAction.ESCALATE

def test_route_admin_action():
    assert compute_routing_action(escalation_type="care_team_handoff") == RoutingAction.ROUTE_ADMIN

def test_reject_action():
    assert compute_routing_action(
        escalation_type="care_team_handoff",
        routing_result={
            "rejected_doctors": [{"reason": "not supported"}]
        }
    ) == RoutingAction.REJECT
    assert compute_routing_action(
        chat_status="routing_ready",
        routing_result={
            "rejected_doctors": [{"reason": "not supported"}]
        }
    ) == RoutingAction.REJECT

def test_book_takes_precedence_over_reject():
    # If there are recommendations AND rejected doctors, it's a BOOK
    assert compute_routing_action(
        chat_status="routing_ready",
        routing_result={
            "web_recommendations": [{"slot": "foo"}],
            "rejected_doctors": [{"reason": "bar"}]
        }
    ) == RoutingAction.BOOK
