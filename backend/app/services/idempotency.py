from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from flask import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import IntegrationEventLog, IntegrationRequestLog

REQUEST_ID_HEADERS = (
    "Idempotency-Key",
    "X-Idempotency-Key",
    "X-Vogent-Request-ID",
    "X-Vogent-Function-Call-ID",
    "X-Elto-Request-ID",
)
REQUEST_ID_FIELDS = ("idempotency_key", "request_id", "function_call_id")
EVENT_ID_FIELDS = ("event_id", "id", "webhook_id")


@dataclass(frozen=True)
class IdempotencyStart:
    log: IntegrationRequestLog
    duplicate_response: dict[str, Any] | None
    duplicate_status_code: int | None

    @property
    def is_duplicate(self) -> bool:
        return self.duplicate_response is not None


@dataclass(frozen=True)
class EventRecord:
    log: IntegrationEventLog
    duplicate: bool


def stable_payload_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _payload_identifier(payload: dict[str, Any], request: Request | None) -> str | None:
    if request is not None:
        for header in REQUEST_ID_HEADERS:
            value = request.headers.get(header)
            if value:
                return value
    for field in REQUEST_ID_FIELDS:
        value = payload.get(field)
        if value:
            return str(value)
    return None


def _event_identifier(payload: dict[str, Any]) -> str | None:
    for field in EVENT_ID_FIELDS:
        value = payload.get(field)
        if value:
            return str(value)
    return None


class IdempotencyService:
    def __init__(self, session: Session):
        self.session = session

    def begin_request(
        self,
        *,
        provider: str,
        operation: str,
        payload: dict[str, Any],
        request: Request | None = None,
        external_id: str | None = None,
    ) -> IdempotencyStart:
        request_hash = stable_payload_hash(payload)
        request_id = external_id or _payload_identifier(payload, request) or f"derived:{request_hash}"
        log = self._request_log(provider=provider, operation=operation, request_id=request_id)
        if log is not None:
            return self._existing_request_start(log, request_hash)

        log = IntegrationRequestLog(
            provider=provider,
            operation=operation,
            external_id=request_id,
            request_hash=request_hash,
            response_json=None,
            status_code=None,
            state="STARTED",
        )
        self.session.add(log)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            log = self._request_log(provider=provider, operation=operation, request_id=request_id)
            if log is None:
                raise
            return self._existing_request_start(log, request_hash)
        return IdempotencyStart(log, None, None)

    def complete_request(self, log: IntegrationRequestLog, *, response: dict[str, Any], status_code: int) -> None:
        log.response_json = response
        log.status_code = status_code
        log.state = "COMPLETED"

    def record_event(
        self,
        *,
        provider: str,
        event_type: str,
        external_call_id: str | None,
        payload: dict[str, Any],
        event_key: str | None = None,
    ) -> EventRecord:
        payload_hash = stable_payload_hash(payload)
        key = event_key or _event_identifier(payload) or f"{event_type}:{external_call_id or 'unknown'}:{payload_hash}"
        log = self._event_log(provider=provider, key=key)
        if log is not None:
            if log.payload_hash != payload_hash:
                raise ApiError(
                    "WEBHOOK_EVENT_KEY_REUSED",
                    "The integration event key was reused with a different payload.",
                    409,
                )
            return EventRecord(log=log, duplicate=True)
        now = datetime.now(UTC)
        log = IntegrationEventLog(
            provider=provider,
            event_key=key,
            event_type=event_type,
            external_call_id=external_call_id,
            payload_hash=payload_hash,
            payload_json=payload,
            status="RECEIVED",
            occurred_at=now,
        )
        self.session.add(log)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            log = self._event_log(provider=provider, key=key)
            if log is None:
                raise
            if log.payload_hash != payload_hash:
                raise ApiError(
                    "WEBHOOK_EVENT_KEY_REUSED",
                    "The integration event key was reused with a different payload.",
                    409,
                ) from None
            return EventRecord(log=log, duplicate=True)
        return EventRecord(log=log, duplicate=False)

    def mark_event_processed(self, log: IntegrationEventLog) -> None:
        log.status = "PROCESSED"
        log.processed_at = datetime.now(UTC)

    def _request_log(self, *, provider: str, operation: str, request_id: str) -> IntegrationRequestLog | None:
        return self.session.scalar(
            select(IntegrationRequestLog).where(
                IntegrationRequestLog.provider == provider,
                IntegrationRequestLog.operation == operation,
                IntegrationRequestLog.external_id == request_id,
            )
        )

    @staticmethod
    def _existing_request_start(log: IntegrationRequestLog, request_hash: str) -> IdempotencyStart:
        if log.request_hash != request_hash:
            raise ApiError(
                "IDEMPOTENCY_KEY_REUSED",
                "The integration idempotency key was reused with a different payload.",
                409,
            )
        if log.state == "COMPLETED" and log.response_json is not None and log.status_code is not None:
            return IdempotencyStart(log, dict(log.response_json), log.status_code)
        raise ApiError("IDEMPOTENT_REQUEST_IN_PROGRESS", "The integration request is already in progress.", 409)

    def _event_log(self, *, provider: str, key: str) -> IntegrationEventLog | None:
        return self.session.scalar(
            select(IntegrationEventLog).where(
                IntegrationEventLog.provider == provider,
                IntegrationEventLog.event_key == key,
            )
        )
