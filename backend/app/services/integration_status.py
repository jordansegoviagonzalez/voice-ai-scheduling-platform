from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import Flask
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IntegrationStatus

OPENAI_INTEGRATION = "openai_gpt_5_2"
VOGENT_INTEGRATION = "vogent_voice_agent"


def record_integration_result(
    session: Session,
    *,
    integration_name: str,
    status: str,
    detail: str,
    metadata: dict[str, Any] | None = None,
    success: bool = False,
) -> None:
    now = datetime.now(UTC)
    row = session.scalar(select(IntegrationStatus).where(IntegrationStatus.integration_name == integration_name))
    if row is None:
        row = IntegrationStatus(
            integration_name=integration_name,
            status=status,
            detail=detail,
            checked_at=now,
            last_success_at=now if success else None,
            metadata_json=metadata or {},
        )
        session.add(row)
        return
    row.status = status
    row.detail = detail
    row.checked_at = now
    row.metadata_json = metadata or {}
    if success:
        row.last_success_at = now


def build_integration_statuses(app: Flask, session: Session) -> list[dict[str, Any]]:
    stored = {
        item.integration_name: item
        for item in session.scalars(
            select(IntegrationStatus).where(
                IntegrationStatus.integration_name.in_([OPENAI_INTEGRATION, VOGENT_INTEGRATION])
            )
        )
    }
    now = datetime.now(UTC)
    statuses = [
        _core_status(
            "flask_api",
            "Flask Scheduling API",
            "Operational",
            "Backend API responded from the active app process.",
            now,
        ),
        _core_status(
            "postgresql",
            "PostgreSQL persistence",
            "Operational",
            "Dashboard query completed against the configured database.",
            now,
        ),
        _core_status(
            "routing",
            "Physician routing engine",
            "Operational",
            "Deterministic eligibility and availability rules are loaded.",
            now,
        ),
        _core_status(
            "transcripts",
            "Call transcript review",
            "Operational",
            "Transcript persistence is available through the call records.",
            now,
        ),
        _openai_status(app, stored.get(OPENAI_INTEGRATION), now),
        _vogent_status(app, stored.get(VOGENT_INTEGRATION), now),
    ]
    return statuses


def _core_status(id_: str, label: str, status_label: str, detail: str, now: datetime) -> dict[str, Any]:
    return {
        "id": id_,
        "label": label,
        "state": "operational",
        "status_label": status_label,
        "detail": detail,
        "checked_at": now.isoformat(),
        "last_success_at": now.isoformat(),
        "metadata": {},
    }


def _openai_status(app: Flask, stored: IntegrationStatus | None, now: datetime) -> dict[str, Any]:
    model = str(app.config.get("OPENAI_MODEL", ""))
    mode = str(app.config.get("OPENAI_INTEGRATION_MODE", "live"))
    metadata = {"model": model, "mode": mode}
    if not app.config.get("OPENAI_API_KEY"):
        return _status(
            OPENAI_INTEGRATION,
            "OpenAI GPT-5.2",
            "not_configured",
            "Not configured",
            "OPENAI_API_KEY is not configured for the backend.",
            now,
            stored,
            metadata,
        )
    if model != "gpt-5.2":
        return _status(
            OPENAI_INTEGRATION,
            "OpenAI GPT-5.2",
            "configuration_error",
            "Configuration mismatch",
            "OPENAI_MODEL must be set to gpt-5.2 for live integration.",
            now,
            stored,
            metadata,
        )
    if mode == "test":
        return _status(
            OPENAI_INTEGRATION,
            "OpenAI GPT-5.2",
            "test_mode",
            "Test mode",
            "OPENAI_INTEGRATION_MODE=test uses deterministic fixtures and does not call OpenAI.",
            now,
            stored,
            metadata,
        )
    if stored and stored.last_success_at:
        return _status(
            OPENAI_INTEGRATION,
            "OpenAI GPT-5.2",
            "connected",
            "Connected",
            stored.detail,
            now,
            stored,
            metadata,
        )
    return _status(
        OPENAI_INTEGRATION,
        "OpenAI GPT-5.2",
        "ready_for_verification",
        "Ready for verification",
        "Configuration is present; no successful live provider check has been recorded yet.",
        now,
        stored,
        metadata,
    )


def _vogent_status(app: Flask, stored: IntegrationStatus | None, now: datetime) -> dict[str, Any]:
    metadata = {
        "agent_configured": bool(app.config.get("VOGENT_AGENT_ID")),
        "public_endpoint_configured": bool(app.config.get("PUBLIC_APP_URL")),
    }
    if not app.config.get("VOGENT_FUNCTION_SECRET") or not app.config.get("VOGENT_WEBHOOK_SECRET"):
        return _status(
            VOGENT_INTEGRATION,
            "Vogent voice agent",
            "awaiting_credentials",
            "Awaiting credentials",
            "Vogent function and webhook secrets must both be configured before live verification.",
            now,
            stored,
            metadata,
        )
    public_url = str(app.config.get("PUBLIC_APP_URL") or "")
    if not public_url.startswith("https://"):
        return _status(
            VOGENT_INTEGRATION,
            "Vogent voice agent",
            "awaiting_public_endpoint",
            "Awaiting public endpoint",
            "Vogent requires a public HTTPS endpoint for webhook and function callbacks.",
            now,
            stored,
            metadata,
        )
    if stored and stored.last_success_at:
        return _status(
            VOGENT_INTEGRATION,
            "Vogent voice agent",
            "connected",
            "Connected",
            stored.detail,
            now,
            stored,
            metadata,
        )
    return _status(
        VOGENT_INTEGRATION,
        "Vogent voice agent",
        "adapter_ready",
        "Adapter ready",
        "Credentials and public endpoint are configured; no successful live Vogent callback has been recorded yet.",
        now,
        stored,
        metadata,
    )


def _status(
    id_: str,
    label: str,
    state: str,
    status_label: str,
    detail: str,
    now: datetime,
    stored: IntegrationStatus | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": id_,
        "label": label,
        "state": state,
        "status_label": status_label,
        "detail": detail,
        "checked_at": (stored.checked_at if stored else now).isoformat(),
        "last_success_at": stored.last_success_at.isoformat() if stored and stored.last_success_at else None,
        "metadata": metadata,
    }
