from __future__ import annotations

import json
from typing import Any, Protocol

from app.integrations.openai.errors import OpenAIIntegrationError
from app.integrations.openai.prompts import SYSTEM_INSTRUCTIONS
from app.integrations.openai.schema import (
    STRUCTURED_INTENT_JSON_SCHEMA,
    StructuredIntent,
    validate_intent_payload,
)


class IntentProvider(Protocol):
    def create_intent_response(self, *, model: str, raw_user_text: str, timeout_seconds: float) -> Any:
        pass


class SDKResponsesProvider:
    def __init__(self, *, api_key: str, max_retries: int):
        try:
            from openai import OpenAI
        except ImportError as error:
            raise OpenAIIntegrationError(
                "OPENAI_SDK_NOT_INSTALLED",
                "The official OpenAI Python SDK is not installed.",
            ) from error
        self.client = OpenAI(api_key=api_key, max_retries=max_retries)

    def create_intent_response(self, *, model: str, raw_user_text: str, timeout_seconds: float) -> Any:
        return self.client.responses.create(
            model=model,
            instructions=SYSTEM_INSTRUCTIONS,
            input=raw_user_text,
            timeout=timeout_seconds,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "caller_scheduling_intent",
                    "schema": STRUCTURED_INTENT_JSON_SCHEMA,
                    "strict": True,
                }
            },
        )


class DeterministicTestProvider:
    def create_intent_response(self, *, model: str, raw_user_text: str, timeout_seconds: float) -> dict[str, Any]:
        lowered = raw_user_text.lower()
        return {
            "raw_user_text": raw_user_text,
            "patient_status": "RETURNING" if "returning" in lowered else "NEW" if "new" in lowered else "UNKNOWN",
            "body_part": _match(lowered, ["Knee", "Hip", "Shoulder", "Hand/Wrist", "Foot/Ankle", "Spine"]),
            "issue_type": _match(lowered, ["Fracture", "Joint Replacement", "Sports Medicine", "General"]),
            "preferred_doctor_name": None,
            "preferred_location_code": None,
            "clarification_required": False,
            "clarification_question": None,
            "caller_correction": None,
        }


class OpenAIIntentAdapter:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        integration_mode: str,
        timeout_seconds: float,
        max_retries: int,
        provider: IntentProvider | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.integration_mode = integration_mode
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.provider = provider

    def extract(
        self,
        *,
        raw_user_text: str,
        known_doctor_names: list[str],
        known_location_codes: set[str],
    ) -> StructuredIntent:
        if not raw_user_text.strip():
            raise OpenAIIntegrationError("OPENAI_INPUT_REQUIRED", "raw_user_text is required.")
        provider = self._provider()
        try:
            response = provider.create_intent_response(
                model=self.model,
                raw_user_text=raw_user_text,
                timeout_seconds=self.timeout_seconds,
            )
        except OpenAIIntegrationError:
            raise
        except TimeoutError as error:
            raise OpenAIIntegrationError("OPENAI_TIMEOUT", "OpenAI request timed out.", retryable=True) from error
        except Exception as error:
            raise self._map_provider_error(error) from error

        payload = self._payload_from_response(response)
        return validate_intent_payload(
            payload,
            known_doctor_names=known_doctor_names,
            known_location_codes=known_location_codes,
        )

    def _provider(self) -> IntentProvider:
        mode = self.integration_mode.lower()
        if self.model != "gpt-5.2":
            raise OpenAIIntegrationError(
                "OPENAI_MODEL_MISMATCH",
                "OPENAI_MODEL must be exactly gpt-5.2. No substitute model will be used.",
            )
        if mode == "test":
            return self.provider or DeterministicTestProvider()
        if mode != "live":
            raise OpenAIIntegrationError("OPENAI_MODE_INVALID", "OPENAI_INTEGRATION_MODE must be live or test.")
        if not self.api_key:
            raise OpenAIIntegrationError("OPENAI_API_KEY_MISSING", "OPENAI_API_KEY is required in live mode.")
        return self.provider or SDKResponsesProvider(api_key=self.api_key, max_retries=self.max_retries)

    def _payload_from_response(self, response: Any) -> dict[str, Any]:
        try:
            if isinstance(response, dict):
                _raise_if_response_failed(response.get("status"), response.get("error"))
                payload = response
            elif isinstance(response, str):
                payload = json.loads(response)
            elif isinstance(getattr(response, "output_text", None), str):
                _raise_if_response_failed(getattr(response, "status", None), getattr(response, "error", None))
                payload = json.loads(response.output_text)
            else:
                _raise_if_response_failed(getattr(response, "status", None), getattr(response, "error", None))
                payload = json.loads(_collect_response_text(response))
        except json.JSONDecodeError as error:
            raise OpenAIIntegrationError(
                "OPENAI_STRUCTURED_OUTPUT_INVALID",
                "OpenAI output was not valid JSON.",
            ) from error
        if not isinstance(payload, dict):
            raise OpenAIIntegrationError("OPENAI_STRUCTURED_OUTPUT_INVALID", "OpenAI output was not a JSON object.")
        return payload

    @staticmethod
    def _map_provider_error(error: Exception) -> OpenAIIntegrationError:
        name = error.__class__.__name__.lower()
        status_code = getattr(error, "status_code", None)
        if "authentication" in name or status_code == 401:
            return OpenAIIntegrationError("OPENAI_AUTHENTICATION_FAILED", "OpenAI authentication failed.")
        if "permission" in name or status_code == 403:
            return OpenAIIntegrationError(
                "OPENAI_MODEL_ACCESS_DENIED",
                "OpenAI account access does not allow the configured model.",
            )
        if "ratelimit" in name or status_code == 429:
            return OpenAIIntegrationError("OPENAI_RATE_LIMITED", "OpenAI rate limit was reached.", retryable=True)
        if "timeout" in name or "apitimeout" in name:
            return OpenAIIntegrationError("OPENAI_TIMEOUT", "OpenAI request timed out.", retryable=True)
        if "connection" in name or "network" in name:
            return OpenAIIntegrationError("OPENAI_NETWORK_ERROR", "OpenAI network request failed.", retryable=True)
        if status_code == 404:
            return OpenAIIntegrationError(
                "OPENAI_MODEL_UNAVAILABLE",
                "The configured OpenAI model was unavailable.",
            )
        if status_code == 400:
            return OpenAIIntegrationError(
                "OPENAI_PROVIDER_CONFIGURATION_ERROR",
                "OpenAI rejected the configured request.",
            )
        if isinstance(status_code, int) and status_code >= 500:
            return OpenAIIntegrationError(
                "OPENAI_PROVIDER_UNAVAILABLE", "OpenAI provider is unavailable.", retryable=True
            )
        return OpenAIIntegrationError("OPENAI_PROVIDER_ERROR", "OpenAI provider request failed.", retryable=True)


def _raise_if_response_failed(status: Any, error: Any) -> None:
    if status in (None, "completed"):
        return
    if error:
        raise OpenAIIntegrationError(
            "OPENAI_PROVIDER_ERROR", "OpenAI response completed with an error.", retryable=True
        )
    raise OpenAIIntegrationError(
        "OPENAI_RESPONSE_INCOMPLETE",
        "OpenAI response did not complete successfully.",
        retryable=True,
    )


def _collect_response_text(response: Any) -> str:
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(str(text))
    if not chunks:
        raise OpenAIIntegrationError("OPENAI_STRUCTURED_OUTPUT_INVALID", "OpenAI response did not include text output.")
    return "".join(chunks)


def _match(value: str, options: list[str]) -> str | None:
    for option in options:
        if option.lower() in value:
            return option
    if "broken" in value or "fracture" in value:
        return "Fracture"
    if "pain" in value:
        return "General"
    return None
