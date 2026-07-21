from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    app_env: str
    secret_key: str
    database_url: str
    frontend_origin: str
    public_app_url: str
    log_level: str
    vogent_api_key: str | None
    vogent_webhook_secret: str | None
    vogent_function_secret: str | None
    vogent_agent_id: str | None
    openai_api_key: str | None
    openai_model: str
    openai_integration_mode: str
    openai_timeout_seconds: float
    openai_max_retries: int
    max_content_length: int
    json_string_field_max_length: int
    raw_user_text_max_length: int
    transcript_turn_max_length: int
    transcript_turn_max_count: int
    rate_limit_enabled: bool
    rate_limit_window_seconds: int
    rate_limit_max_requests: int

    @classmethod
    def from_env(cls) -> Config:
        app_env = os.getenv("APP_ENV", "development").strip().lower()
        database_url = os.getenv("DATABASE_URL")
        secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")
        openai_integration_mode = os.getenv("OPENAI_INTEGRATION_MODE", "live").strip().lower()
        _validate_runtime_config(
            app_env=app_env,
            database_url=database_url,
            secret_key=secret_key,
            openai_integration_mode=openai_integration_mode,
        )
        return cls(
            app_env=app_env,
            secret_key=secret_key,
            database_url=database_url or "",
            frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
            public_app_url=os.getenv("PUBLIC_APP_URL", "http://localhost:5173"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            vogent_api_key=os.getenv("VOGENT_API_KEY"),
            vogent_webhook_secret=os.getenv("VOGENT_WEBHOOK_SECRET"),
            vogent_function_secret=os.getenv("VOGENT_FUNCTION_SECRET"),
            vogent_agent_id=os.getenv("VOGENT_AGENT_ID"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.2"),
            openai_integration_mode=openai_integration_mode,
            openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "8")),
            openai_max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
            max_content_length=int(os.getenv("MAX_CONTENT_LENGTH", str(256 * 1024))),
            json_string_field_max_length=int(os.getenv("JSON_STRING_FIELD_MAX_LENGTH", "8192")),
            raw_user_text_max_length=int(os.getenv("RAW_USER_TEXT_MAX_LENGTH", "4000")),
            transcript_turn_max_length=int(os.getenv("TRANSCRIPT_TURN_MAX_LENGTH", "2000")),
            transcript_turn_max_count=int(os.getenv("TRANSCRIPT_TURN_MAX_COUNT", "200")),
            rate_limit_enabled=_bool_env("RATE_LIMIT_ENABLED", default=app_env != "test"),
            rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
            rate_limit_max_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60")),
        )


def _validate_runtime_config(
    *,
    app_env: str,
    database_url: str | None,
    secret_key: str,
    openai_integration_mode: str,
) -> None:
    if not database_url:
        raise ConfigError("DATABASE_URL is required. Configure PostgreSQL for normal runtime.")
    if app_env != "test" and database_url.startswith("sqlite"):
        raise ConfigError("SQLite is allowed only for explicit test configuration; use PostgreSQL for runtime.")
    if app_env == "production":
        if not database_url.startswith("postgresql"):
            raise ConfigError("Production DATABASE_URL must use PostgreSQL.")
        if secret_key in {"dev-only-change-me", "local-development-key", "replace-with-a-long-random-value"}:
            raise ConfigError("Production SECRET_KEY must be set to a strong non-development value.")
        if openai_integration_mode == "test" and os.getenv("ALLOW_OPENAI_TEST_MODE_IN_PRODUCTION") != "true":
            raise ConfigError("Production cannot use OPENAI_INTEGRATION_MODE=test without explicit approval.")


def _bool_env(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
