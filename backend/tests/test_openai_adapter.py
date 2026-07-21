from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import pytest

from app.integrations.openai import OpenAIIntegrationError, OpenAIIntentAdapter
from app.integrations.openai.client import SDKResponsesProvider

DOCTORS = ["Dr. Elena Vasquez", "Dr. James Walsh"]
LOCATIONS = {"MAIN", "NORTH"}


class FakeProvider:
    def __init__(self, payload: Any):
        self.payload = payload

    def create_intent_response(self, *, model: str, raw_user_text: str, timeout_seconds: float) -> Any:
        if isinstance(self.payload, Exception):
            raise self.payload
        if isinstance(self.payload, dict):
            return dict(self.payload)
        return self.payload


def _adapter(payload: Any, *, mode: str = "test", model: str = "gpt-5.2") -> OpenAIIntentAdapter:
    return OpenAIIntentAdapter(
        api_key="test-key" if mode == "live" else None,
        model=model,
        integration_mode=mode,
        timeout_seconds=1,
        max_retries=0,
        provider=FakeProvider(payload),
    )


def _payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "raw_user_text": "I am a new patient with a shoulder fracture and prefer Dr. Vasquez.",
        "patient_status": "NEW",
        "body_part": "Shoulder",
        "issue_type": "Fracture",
        "preferred_doctor_name": "Dr. Elena Vasquez",
        "preferred_location_code": "MAIN",
        "clarification_required": False,
        "clarification_question": None,
        "caller_correction": None,
    }
    payload.update(overrides)
    return payload


def test_openai_adapter_validates_structured_intent() -> None:
    intent = _adapter(_payload()).extract(
        raw_user_text="shoulder fracture",
        known_doctor_names=DOCTORS,
        known_location_codes=LOCATIONS,
    )
    assert intent.patient_status == "NEW"
    assert intent.body_part == "Shoulder"
    assert intent.issue_type == "Fracture"
    assert intent.preferred_doctor_name == "Dr. Elena Vasquez"


def test_openai_adapter_rejects_invalid_enums_and_hallucinated_roster_items() -> None:
    with pytest.raises(OpenAIIntegrationError, match="Body part"):
        _adapter(_payload(body_part="Elbow")).extract(
            raw_user_text="elbow pain",
            known_doctor_names=DOCTORS,
            known_location_codes=LOCATIONS,
        )
    with pytest.raises(OpenAIIntegrationError, match="Preferred physician"):
        _adapter(_payload(preferred_doctor_name="Dr. Not Real")).extract(
            raw_user_text="doctor preference",
            known_doctor_names=DOCTORS,
            known_location_codes=LOCATIONS,
        )
    with pytest.raises(OpenAIIntegrationError, match="Preferred location"):
        _adapter(_payload(preferred_location_code="SOUTH")).extract(
            raw_user_text="location preference",
            known_doctor_names=DOCTORS,
            known_location_codes=LOCATIONS,
        )


def test_openai_live_mode_fails_closed_without_key_and_without_model_substitution() -> None:
    missing_key = OpenAIIntentAdapter(
        api_key=None,
        model="gpt-5.2",
        integration_mode="live",
        timeout_seconds=1,
        max_retries=0,
    )
    with pytest.raises(OpenAIIntegrationError) as error:
        missing_key.extract(raw_user_text="knee pain", known_doctor_names=DOCTORS, known_location_codes=LOCATIONS)
    assert error.value.code == "OPENAI_API_KEY_MISSING"

    with pytest.raises(OpenAIIntegrationError) as mismatch:
        _adapter(_payload(), model="gpt-5.6-terra").extract(
            raw_user_text="knee pain",
            known_doctor_names=DOCTORS,
            known_location_codes=LOCATIONS,
        )
    assert mismatch.value.code == "OPENAI_MODEL_MISMATCH"


def test_openai_adapter_maps_provider_timeout() -> None:
    with pytest.raises(OpenAIIntegrationError) as error:
        _adapter(TimeoutError("slow")).extract(
            raw_user_text="knee pain",
            known_doctor_names=DOCTORS,
            known_location_codes=LOCATIONS,
        )
    assert error.value.code == "OPENAI_TIMEOUT"
    assert error.value.retryable is True


@pytest.mark.parametrize(
    ("provider_error", "expected_code", "retryable"),
    [
        (
            type("AuthenticationError", (Exception,), {"status_code": 401})("bad key"),
            "OPENAI_AUTHENTICATION_FAILED",
            False,
        ),
        (
            type("PermissionDeniedError", (Exception,), {"status_code": 403})("no model"),
            "OPENAI_MODEL_ACCESS_DENIED",
            False,
        ),
        (type("NotFoundError", (Exception,), {"status_code": 404})("missing model"), "OPENAI_MODEL_UNAVAILABLE", False),
        (type("RateLimitError", (Exception,), {"status_code": 429})("rate"), "OPENAI_RATE_LIMITED", True),
        (type("APIConnectionError", (Exception,), {})("network"), "OPENAI_NETWORK_ERROR", True),
        (
            type("InternalServerError", (Exception,), {"status_code": 500})("server"),
            "OPENAI_PROVIDER_UNAVAILABLE",
            True,
        ),
    ],
)
def test_openai_adapter_maps_provider_failures(
    provider_error: Exception,
    expected_code: str,
    retryable: bool,
) -> None:
    with pytest.raises(OpenAIIntegrationError) as error:
        _adapter(provider_error).extract(
            raw_user_text="knee pain",
            known_doctor_names=DOCTORS,
            known_location_codes=LOCATIONS,
        )
    assert error.value.code == expected_code
    assert error.value.retryable is retryable


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "not-json",
        {"status": "incomplete", "output": []},
        _payload(extra_field="not allowed"),
        {key: value for key, value in _payload().items() if key != "issue_type"},
        _payload(caller_correction={"issue_type": "General", "unsupported": "x"}),
    ],
)
def test_openai_adapter_rejects_empty_malformed_missing_or_extra_output(payload: Any) -> None:
    with pytest.raises(OpenAIIntegrationError):
        _adapter(payload).extract(
            raw_user_text="knee pain",
            known_doctor_names=DOCTORS,
            known_location_codes=LOCATIONS,
        )


def test_openai_adapter_rejects_medical_or_booking_claims() -> None:
    with pytest.raises(OpenAIIntegrationError) as error:
        _adapter(
            _payload(
                clarification_required=True,
                clarification_question="Your appointment is confirmed. Also take medication.",
            )
        ).extract(
            raw_user_text="please book it",
            known_doctor_names=DOCTORS,
            known_location_codes=LOCATIONS,
        )
    assert error.value.code == "OPENAI_BOUNDARY_VIOLATION"


def test_sdk_responses_provider_constructs_official_structured_output_request(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    class FakeResponses:
        def create(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return _payload()

    class FakeOpenAI:
        def __init__(self, *, api_key: str, max_retries: int):
            assert api_key == "key"
            assert max_retries == 2
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    provider = SDKResponsesProvider(api_key="key", max_retries=2)
    provider.create_intent_response(model="gpt-5.2", raw_user_text="shoulder fracture", timeout_seconds=8)

    assert calls[0]["model"] == "gpt-5.2"
    assert calls[0]["input"] == "shoulder fracture"
    assert calls[0]["timeout"] == 8
    assert calls[0]["text"]["format"]["type"] == "json_schema"
    assert calls[0]["text"]["format"]["strict"] is True
    assert calls[0]["text"]["format"]["schema"]["additionalProperties"] is False


@pytest.mark.parametrize(
    "unsafe_question",
    [
        "I can draft a SOAP note for this injury.",
        "The ICD code is ready.",
        "Please provide the patient ID and slot ID.",
    ],
)
def test_openai_adapter_rejects_scribe_coding_and_internal_id_output(unsafe_question: str) -> None:
    with pytest.raises(OpenAIIntegrationError) as error:
        _adapter(
            _payload(
                clarification_required=True,
                clarification_question=unsafe_question,
            )
        ).extract(
            raw_user_text="please help",
            known_doctor_names=DOCTORS,
            known_location_codes=LOCATIONS,
        )
    assert error.value.code == "OPENAI_BOUNDARY_VIOLATION"
