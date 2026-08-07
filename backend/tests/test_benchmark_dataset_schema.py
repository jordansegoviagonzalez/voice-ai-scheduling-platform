"""
Lightweight schema validation for backend/tests/fixtures/benchmark_scenarios_v1.json.

This test:
- Loads the JSON dataset from the fixtures path.
- Verifies the dataset can be parsed as valid JSON.
- Verifies all scenario_ids are unique.
- Verifies all required fields exist on every scenario.
- Verifies expected_output.action values are from the allowed set.
- Verifies channel values are from the allowed set.
- Verifies expected_features is a non-empty dict.
- Verifies expected_output is a dict with at least an action key.
- Verifies tags is a non-empty list.
- Verifies trace_expectation is present and non-empty.

Does NOT:
- Call GPT-5.2 or any AI provider.
- Call LangSmith.
- Book appointments.
- Require network access.
- Use real patient data.
- Modify the dataset file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "benchmark_scenarios_v1.json"

ALLOWED_ACTIONS = {
    "book_or_offer_valid_slot",
    "book_or_clarify",
    "clarify",
    "clarify_or_book",
    "clarify_or_escalate_if_red_flags",
    "clarify_or_no_match",
    "clarify_or_refer",
    "clarify_or_route",
    "clarify_or_route_nonbooking",
    "escalate",
    "offer_alternative",
    "offer_fallback",
    "offer_fallback_or_waitlist",
    "reject_or_clarify",
    "reject_or_error",
    "reject_or_no_match",
    "reject_or_redirect",
    "reject_or_retry",
    "route_or_clarify_nonbooking",
    "route_or_schedule_followup",
    "same_decision_across_channels",
    "same_nonbooking_decision_across_channels",
    "urgent_route_or_escalate",
}

ALLOWED_CHANNELS = {"voice", "chat", "both"}

REQUIRED_SCENARIO_FIELDS = [
    "scenario_id",
    "patient_input",
    "expected_features",
    "expected_output",
    "tags",
    "trace_expectation",
    "channel",
]


def load_dataset() -> dict:
    assert FIXTURES_PATH.exists(), (
        f"Dataset file not found: {FIXTURES_PATH}. "
        "Place benchmark_scenarios_v1.json at backend/tests/fixtures/ before running this test."
    )
    with open(FIXTURES_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_dataset_json_loads() -> None:
    """The dataset file must be valid JSON."""
    data = load_dataset()
    assert isinstance(data, dict), "Dataset root must be a JSON object."
    assert "scenarios" in data, "Dataset must have a 'scenarios' key."
    assert isinstance(data["scenarios"], list), "'scenarios' must be a list."
    assert len(data["scenarios"]) > 0, "'scenarios' list must not be empty."


def test_scenario_ids_are_unique() -> None:
    """Every scenario must have a unique scenario_id."""
    data = load_dataset()
    scenarios = data["scenarios"]
    ids = [s.get("scenario_id") for s in scenarios]
    missing_ids = [i for i, sid in enumerate(ids) if not sid]
    assert not missing_ids, f"Scenarios at indexes {missing_ids} are missing scenario_id."
    duplicates = {sid for sid in ids if ids.count(sid) > 1}
    assert not duplicates, f"Duplicate scenario_ids found: {sorted(duplicates)}"


def test_required_fields_exist_on_every_scenario() -> None:
    """Every scenario must have all required fields present and non-null."""
    data = load_dataset()
    errors: list[str] = []
    for scenario in data["scenarios"]:
        sid = scenario.get("scenario_id", "<missing_id>")
        for field in REQUIRED_SCENARIO_FIELDS:
            if field not in scenario or scenario[field] is None:
                errors.append(f"scenario_id={sid!r}: missing or null field '{field}'")
    assert not errors, "Required field violations:\n" + "\n".join(errors)


def test_expected_action_values_are_allowed() -> None:
    """expected_output.action must be one of the allowed action values."""
    data = load_dataset()
    errors: list[str] = []
    for scenario in data["scenarios"]:
        sid = scenario.get("scenario_id", "<missing_id>")
        eo = scenario.get("expected_output")
        if not isinstance(eo, dict):
            errors.append(f"scenario_id={sid!r}: expected_output is not a dict")
            continue
        action = eo.get("action")
        if action not in ALLOWED_ACTIONS:
            errors.append(
                f"scenario_id={sid!r}: expected_output.action={action!r} is not in allowed set"
            )
    assert not errors, "Action value violations:\n" + "\n".join(errors)


def test_channel_values_are_allowed() -> None:
    """channel must be one of: voice, chat, both."""
    data = load_dataset()
    errors: list[str] = []
    for scenario in data["scenarios"]:
        sid = scenario.get("scenario_id", "<missing_id>")
        channel = scenario.get("channel")
        if channel not in ALLOWED_CHANNELS:
            errors.append(
                f"scenario_id={sid!r}: channel={channel!r} is not in {ALLOWED_CHANNELS}"
            )
    assert not errors, "Channel value violations:\n" + "\n".join(errors)


def test_expected_features_is_nonempty_dict() -> None:
    """expected_features must be a non-empty dict on every scenario."""
    data = load_dataset()
    errors: list[str] = []
    for scenario in data["scenarios"]:
        sid = scenario.get("scenario_id", "<missing_id>")
        ef = scenario.get("expected_features")
        if not isinstance(ef, dict) or len(ef) == 0:
            errors.append(f"scenario_id={sid!r}: expected_features is missing or empty")
    assert not errors, "expected_features violations:\n" + "\n".join(errors)


def test_expected_output_has_action_key() -> None:
    """expected_output must be a dict containing at least an 'action' key."""
    data = load_dataset()
    errors: list[str] = []
    for scenario in data["scenarios"]:
        sid = scenario.get("scenario_id", "<missing_id>")
        eo = scenario.get("expected_output")
        if not isinstance(eo, dict):
            errors.append(f"scenario_id={sid!r}: expected_output is not a dict")
        elif "action" not in eo:
            errors.append(f"scenario_id={sid!r}: expected_output missing 'action' key")
    assert not errors, "expected_output violations:\n" + "\n".join(errors)


def test_tags_is_nonempty_list() -> None:
    """tags must be a non-empty list on every scenario."""
    data = load_dataset()
    errors: list[str] = []
    for scenario in data["scenarios"]:
        sid = scenario.get("scenario_id", "<missing_id>")
        tags = scenario.get("tags")
        if not isinstance(tags, list) or len(tags) == 0:
            errors.append(f"scenario_id={sid!r}: tags is missing or empty")
    assert not errors, "tags violations:\n" + "\n".join(errors)


def test_trace_expectation_is_present_and_nonempty() -> None:
    """trace_expectation must be present and non-empty on every scenario."""
    data = load_dataset()
    errors: list[str] = []
    for scenario in data["scenarios"]:
        sid = scenario.get("scenario_id", "<missing_id>")
        te = scenario.get("trace_expectation")
        if not te or (isinstance(te, (str, dict, list)) and len(te) == 0):
            errors.append(f"scenario_id={sid!r}: trace_expectation is missing or empty")
    assert not errors, "trace_expectation violations:\n" + "\n".join(errors)


def test_dataset_scenario_count_matches_metadata() -> None:
    """The actual scenario count must match the dataset's declared scenario_count if present."""
    data = load_dataset()
    declared = data.get("scenario_count")
    actual = len(data["scenarios"])
    if declared is not None:
        assert actual == declared, (
            f"Dataset declares scenario_count={declared} but actual scenario count is {actual}."
        )
