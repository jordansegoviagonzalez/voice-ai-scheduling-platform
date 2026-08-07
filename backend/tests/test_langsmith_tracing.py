import os
import pytest
from app.observability.langsmith_tracing import (
    is_langsmith_enabled,
    sanitize_trace_inputs,
    safe_traceable,
    wrap_openai_if_enabled,
    HAS_LANGSMITH
)

def test_is_langsmith_enabled_default_false(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    assert not is_langsmith_enabled()

def test_is_langsmith_enabled_true(monkeypatch):
    if HAS_LANGSMITH:
        monkeypatch.setenv("LANGSMITH_TRACING", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "test-key")
        assert is_langsmith_enabled()

def test_sanitize_trace_inputs():
    inputs = {
        "scenario_id": "BENCH-001",
        "patient_name": "John Doe",
        "first_name": "John",
        "last_name": "Doe",
        "dob": "1990-01-01",
        "phone": "555-1234",
        "email": "john@example.com",
        "address": "123 Main St",
        "transcript": "Hello, I need a doctor.",
        "patient_input": "My knee hurts.",
        "nested": {
            "phone": "555-5678",
            "safe_data": "value"
        },
        "list_data": [
            {"email": "test@test.com", "other": "ok"}
        ]
    }

    sanitized = sanitize_trace_inputs(inputs)

    assert sanitized["scenario_id"] == "BENCH-001"
    assert sanitized["patient_name"] == "[REDACTED]"
    assert sanitized["first_name"] == "[REDACTED]"
    assert sanitized["last_name"] == "[REDACTED]"
    assert sanitized["dob"] == "[REDACTED]"
    assert sanitized["phone"] == "[REDACTED]"
    assert sanitized["email"] == "[REDACTED]"
    assert sanitized["address"] == "[REDACTED]"
    assert sanitized["transcript"] == "[REDACTED]"
    assert sanitized["patient_input"] == "[REDACTED]"
    assert sanitized["nested"]["phone"] == "[REDACTED]"
    assert sanitized["nested"]["safe_data"] == "value"
    assert sanitized["list_data"][0]["email"] == "[REDACTED]"
    assert sanitized["list_data"][0]["other"] == "ok"

def test_safe_traceable_decorator_passthrough(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)

    @safe_traceable(name="Test Func")
    def my_func(x):
        return x * 2

    assert my_func(5) == 10

def test_wrap_openai_if_enabled_passthrough(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    class DummyClient:
        pass
    client = DummyClient()
    wrapped = wrap_openai_if_enabled(client)
    assert wrapped is client
