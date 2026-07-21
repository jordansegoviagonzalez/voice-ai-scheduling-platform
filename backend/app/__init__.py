from __future__ import annotations

import uuid

from flask import Flask, g, request
from flask_cors import CORS

from app.config import Config
from app.errors import register_error_handlers
from app.extensions import init_database
from app.logging_config import configure_logging
from app.routes import api_blueprint
from app.seed.command import register_seed_command
from app.services.rate_limit import enforce_rate_limit


def create_app(test_config: dict[str, object] | None = None) -> Flask:
    settings = Config.from_env()
    configure_logging(settings.log_level)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.secret_key,
        DATABASE_URL=settings.database_url,
        APP_ENV=settings.app_env,
        FRONTEND_ORIGIN=settings.frontend_origin,
        PUBLIC_APP_URL=settings.public_app_url,
        VOGENT_API_KEY=settings.vogent_api_key,
        VOGENT_WEBHOOK_SECRET=settings.vogent_webhook_secret,
        VOGENT_FUNCTION_SECRET=settings.vogent_function_secret,
        VOGENT_AGENT_ID=settings.vogent_agent_id,
        OPENAI_API_KEY=settings.openai_api_key,
        OPENAI_MODEL=settings.openai_model,
        OPENAI_INTEGRATION_MODE=settings.openai_integration_mode,
        OPENAI_TIMEOUT_SECONDS=settings.openai_timeout_seconds,
        OPENAI_MAX_RETRIES=settings.openai_max_retries,
        MAX_CONTENT_LENGTH=settings.max_content_length,
        JSON_STRING_FIELD_MAX_LENGTH=settings.json_string_field_max_length,
        RAW_USER_TEXT_MAX_LENGTH=settings.raw_user_text_max_length,
        TRANSCRIPT_TURN_MAX_LENGTH=settings.transcript_turn_max_length,
        TRANSCRIPT_TURN_MAX_COUNT=settings.transcript_turn_max_count,
        RATE_LIMIT_ENABLED=settings.rate_limit_enabled,
        RATE_LIMIT_WINDOW_SECONDS=settings.rate_limit_window_seconds,
        RATE_LIMIT_MAX_REQUESTS=settings.rate_limit_max_requests,
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)

    CORS(app, origins=[app.config["FRONTEND_ORIGIN"]], supports_credentials=False)
    init_database(app)
    register_error_handlers(app)
    register_seed_command(app)
    app.register_blueprint(api_blueprint, url_prefix="/api/v1")

    @app.before_request
    def assign_request_id() -> None:
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    @app.before_request
    def apply_rate_limit() -> None:
        enforce_rate_limit(app)

    @app.after_request
    def add_request_id(response):  # type: ignore[no-untyped-def]
        response.headers["X-Request-ID"] = g.request_id
        return response

    return app
