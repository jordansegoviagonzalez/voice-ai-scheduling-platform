import os
import functools
from typing import Any, Callable, Dict, Optional, TypeVar

try:
    from langsmith import traceable, Client
    import langsmith
    HAS_LANGSMITH = True
except ImportError:
    HAS_LANGSMITH = False

F = TypeVar('F', bound=Callable[..., Any])

def is_langsmith_enabled() -> bool:
    return (
        HAS_LANGSMITH and
        os.environ.get("LANGSMITH_TRACING", "").lower() == "true" and
        bool(os.environ.get("LANGCHAIN_API_KEY"))
    )

def _sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields from dictionaries."""
    sanitized = {}
    sensitive_keys = {"patient_name", "first_name", "last_name", "dob", "phone", "email", "address", "transcript", "patient_input"}
    for k, v in data.items():
        if k.lower() in sensitive_keys:
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_dict(v)
        elif isinstance(v, list):
            sanitized[k] = [_sanitize_dict(item) if isinstance(item, dict) else item for item in v]
        else:
            sanitized[k] = v
    return sanitized

def sanitize_trace_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return _sanitize_dict(inputs)

def sanitize_trace_outputs(outputs: dict[str, Any] | Any) -> dict[str, Any] | Any:
    if isinstance(outputs, dict):
        return _sanitize_dict(outputs)
    return outputs

def safe_traceable(
    name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list[str]] = None,
) -> Callable[[F], F]:
    """
    Decorator that applies langsmith @traceable only if tracing is fully enabled.
    Otherwise, it acts as a no-op passthrough decorator.
    """
    def decorator(func: F) -> F:
        if is_langsmith_enabled():
            return traceable(
                name=name or func.__name__,
                metadata=metadata,
                tags=tags,
                process_inputs=sanitize_trace_inputs,
                process_outputs=sanitize_trace_outputs
            )(func)
        return func
    return decorator

def wrap_openai_if_enabled(client: Any) -> Any:
    if is_langsmith_enabled() and hasattr(langsmith, "wrappers"):
        from langsmith.wrappers import wrap_openai
        return wrap_openai(client)
    return client

def trace_benchmark_evaluation(scenario: dict[str, Any], actual_action: str, is_pass: bool) -> None:
    if not is_langsmith_enabled():
        return

    try:
        from langsmith import trace
        with trace(
            "Benchmark Scenario Evaluation",
            project_name=os.environ.get("LANGCHAIN_PROJECT", "default"),
            run_type="evaluation",
            tags=[
                scenario.get("channel", "unknown"),
                scenario.get("org_slug", "unknown"),
                scenario.get("cdc_module", "unknown"),
            ],
            metadata={
                "scenario_id": scenario.get("scenario_id"),
                "channel": scenario.get("channel"),
                "org_slug": scenario.get("org_slug"),
                "source_basis": scenario.get("source_basis"),
                "cdc_module": scenario.get("cdc_module"),
                "product_risk_category": scenario.get("product_risk_category"),
                "expected_action_raw": scenario.get("expected_output", {}).get("action"),
                "actual_routing_action": actual_action,
                "benchmark_passed": is_pass,
                "patient_type": scenario.get("expected_features", {}).get("patient_type"),
                "body_part": scenario.get("expected_features", {}).get("body_part"),
                "issue_type": scenario.get("expected_features", {}).get("issue_type"),
                "urgency": scenario.get("expected_features", {}).get("urgency"),
            },
            inputs=sanitize_trace_inputs(scenario),
            outputs={"actual_action": actual_action, "is_pass": is_pass}
        ) as rt:
            pass
    except Exception:
        pass
