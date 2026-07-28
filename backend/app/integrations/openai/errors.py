from __future__ import annotations


class OpenAIIntegrationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        provider_error: dict[str, object | None] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.provider_error = provider_error or {}
