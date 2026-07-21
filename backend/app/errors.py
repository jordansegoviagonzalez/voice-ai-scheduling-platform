from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from flask import Flask, g, jsonify
from werkzeug.exceptions import HTTPException


@dataclass
class ApiError(Exception):
    code: str
    message: str
    status_code: int = 400
    field_errors: dict[str, list[str]] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):  # type: ignore[no-untyped-def]
        body = {
            "error": {
                "code": error.code,
                "message": error.message,
                "field_errors": error.field_errors,
                "request_id": getattr(g, "request_id", None),
            }
        }
        if error.details:
            body["error"]["details"] = error.details
        return jsonify(body), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):  # type: ignore[no-untyped-def]
        return (
            jsonify(
                {
                    "error": {
                        "code": error.name.upper().replace(" ", "_"),
                        "message": error.description,
                        "field_errors": {},
                        "request_id": getattr(g, "request_id", None),
                    }
                }
            ),
            error.code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):  # type: ignore[no-untyped-def]
        app.logger.exception("Unhandled request error")
        return (
            jsonify(
                {
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred.",
                        "field_errors": {},
                        "request_id": getattr(g, "request_id", None),
                    }
                }
            ),
            500,
        )
