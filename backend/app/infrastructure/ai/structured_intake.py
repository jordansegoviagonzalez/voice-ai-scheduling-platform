import json
import logging
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.domain.chat.chat_types import ChatModelResponse
from app.integrations.openai.errors import OpenAIIntegrationError

logger = logging.getLogger(__name__)


def get_intake_system_prompt() -> str:
    prompt_path = Path(__file__).parent / "prompts" / "intake_system_prompt.txt"
    with open(prompt_path, encoding="utf-8") as f:
        return f.read()


STRUCTURED_INTAKE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "assistant_message": {"type": "string"},
        "extracted_fields": {
            "type": "object",
            "properties": {
                "patient_type": {"type": ["string", "null"], "enum": ["new", "returning", None]},
                "full_name": {"type": ["string", "null"]},
                "date_of_birth": {"type": ["string", "null"]},
                "phone": {"type": ["string", "null"]},
                "email": {"type": ["string", "null"]},
                "insurance_provider": {"type": ["string", "null"]},
                "chief_complaint": {"type": ["string", "null"]},
                "body_part": {
                    "type": ["string", "null"],
                    "enum": [
                        "Knee",
                        "Hip",
                        "Shoulder",
                        "Upper Arm",
                        "Elbow",
                        "Forearm",
                        "Hand/Wrist",
                        "Upper Leg",
                        "Lower Leg",
                        "Foot/Ankle",
                        "Spine",
                        None,
                    ],
                },
                "side": {"type": ["string", "null"], "enum": ["left", "right", "bilateral", "not_applicable", None]},
                "symptom_duration": {"type": ["string", "null"]},
                "severity": {"type": ["integer", "null"]},
                "appointment_type": {
                    "type": ["string", "null"],
                    "enum": ["new_patient", "follow_up", "post_op", "urgent", None],
                },
                "issue_type": {
                    "type": ["string", "null"],
                    "enum": ["Fracture", "Joint Replacement", "Sports Medicine", "General", None],
                },
                "preferred_location": {
                    "type": ["string", "null"],
                    "enum": ["MAIN", "EAST", "NORTH", "WEST", "SOUTH", "ANY", None],
                },
                "preferred_date_or_time": {"type": ["string", "null"]},
                "preferred_time_of_day": {"type": ["string", "null"], "enum": ["morning", "afternoon", "any", None]},
                "preferred_physician": {"type": ["string", "null"]},
            },
            "required": [
                "appointment_type",
                "body_part",
                "chief_complaint",
                "date_of_birth",
                "email",
                "full_name",
                "insurance_provider",
                "issue_type",
                "patient_type",
                "phone",
                "preferred_date_or_time",
                "preferred_location",
                "preferred_physician",
                "preferred_time_of_day",
                "severity",
                "side",
                "symptom_duration",
            ],
            "additionalProperties": False,
        },
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "old_value": {"type": "string"},
                    "new_value": {"type": "string"},
                },
                "required": ["field", "old_value", "new_value"],
                "additionalProperties": False,
            },
        },
        "off_topic": {"type": "boolean"},
        "possible_emergency": {"type": "boolean"},
        "handoff_requested": {"type": "boolean"},
        "confidence": {"type": "number"},
    },
    "required": [
        "intent",
        "assistant_message",
        "extracted_fields",
        "corrections",
        "off_topic",
        "possible_emergency",
        "handoff_requested",
        "confidence",
    ],
    "additionalProperties": False,
}


class OpenAIIntakeClient:
    def __init__(
        self,
        api_key: str | None,
        model: str = "gpt-5.2",
        *,
        timeout_seconds: float = 8,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.client: Any | None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, max_retries=max_retries)
        else:
            self.client = None

    def analyze_message(
        self, current_state: str, recent_messages: list[dict[str, str]], latest_message: str, required_fields: list[str]
    ) -> ChatModelResponse:
        if not self.client:
            raise OpenAIIntegrationError(
                "OPENAI_API_KEY_MISSING",
                "OPENAI_API_KEY is required for live intake interpretation.",
            )

        system_prompt = get_intake_system_prompt()
        context = f"Current state: {current_state}\nMissing required fields to collect next: {required_fields}\n"
        input_messages: list[dict[str, str]] = []
        for m in recent_messages[-5:]:
            role = "user" if m["role"] == "patient" else "assistant"
            input_messages.append({"role": role, "content": m["content"]})
        input_messages.append({"role": "user", "content": latest_message})

        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=system_prompt + "\n" + context,
                input=input_messages,
                timeout=self.timeout_seconds,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "intake_response",
                        "schema": STRUCTURED_INTAKE_SCHEMA,
                        "strict": True,
                    }
                },
            )
        except Exception as error:
            mapped = _map_provider_error(error)
            if mapped.provider_error:
                logger.warning(
                    "OpenAI intake provider request failed",
                    extra={"provider_error": mapped.provider_error},
                )
            raise mapped from error

        try:
            content = response.output_text
            return json.loads(content)
        except json.JSONDecodeError as error:
            raise OpenAIIntegrationError(
                "OPENAI_STRUCTURED_OUTPUT_INVALID",
                "OpenAI intake output was not valid JSON.",
            ) from error
        except AttributeError as error:
            raise OpenAIIntegrationError(
                "OPENAI_STRUCTURED_OUTPUT_INVALID",
                "OpenAI intake response did not include output_text.",
            ) from error


def _map_provider_error(error: Exception) -> OpenAIIntegrationError:
    status_code = getattr(error, "status_code", None)
    provider_error = _provider_error_metadata(error)
    if status_code == 400:
        return OpenAIIntegrationError(
            "OPENAI_PROVIDER_CONFIGURATION_ERROR",
            "OpenAI rejected the configured intake request.",
            provider_error=provider_error,
        )
    if status_code == 401:
        return OpenAIIntegrationError(
            "OPENAI_AUTHENTICATION_FAILED",
            "OpenAI authentication failed.",
            provider_error=provider_error,
        )
    if status_code == 403:
        return OpenAIIntegrationError(
            "OPENAI_MODEL_ACCESS_DENIED",
            "OpenAI account access does not allow the configured model.",
            provider_error=provider_error,
        )
    if status_code == 429:
        return OpenAIIntegrationError(
            "OPENAI_RATE_LIMITED",
            "OpenAI rate limit was reached.",
            retryable=True,
            provider_error=provider_error,
        )
    if isinstance(status_code, int) and status_code >= 500:
        return OpenAIIntegrationError(
            "OPENAI_PROVIDER_UNAVAILABLE",
            "OpenAI provider is unavailable.",
            retryable=True,
            provider_error=provider_error,
        )
    name = error.__class__.__name__.lower()
    if "timeout" in name:
        return OpenAIIntegrationError(
            "OPENAI_TIMEOUT",
            "OpenAI request timed out.",
            retryable=True,
            provider_error=provider_error,
        )
    if "connection" in name or "network" in name:
        return OpenAIIntegrationError(
            "OPENAI_NETWORK_ERROR",
            "OpenAI network request failed.",
            retryable=True,
            provider_error=provider_error,
        )
    return OpenAIIntegrationError(
        "OPENAI_PROVIDER_ERROR",
        "OpenAI provider request failed.",
        retryable=True,
        provider_error=provider_error,
    )


def _provider_error_metadata(error: Exception) -> dict[str, object | None]:
    response = getattr(error, "response", None)
    body: dict[str, Any] | None = None
    if response is not None:
        try:
            parsed = response.json()
            body = parsed if isinstance(parsed, dict) else None
        except Exception:
            body = None
    error_body = body.get("error") if isinstance(body, dict) else None
    return {
        "provider": "openai",
        "http_status": getattr(error, "status_code", None),
        "error_code": error_body.get("code") if isinstance(error_body, dict) else getattr(error, "code", None),
        "error_type": error_body.get("type") if isinstance(error_body, dict) else getattr(error, "type", None),
        "rejected_parameter": (
            error_body.get("param") if isinstance(error_body, dict) else getattr(error, "param", None)
        ),
        "request_id": getattr(error, "request_id", None),
    }
