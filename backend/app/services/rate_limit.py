from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from flask import Flask, Request, request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.errors import ApiError
from app.extensions import get_session
from app.models import ApiRateLimitBucket

PROTECTED_ENDPOINTS = {
    "appointments.create_appointment",
    "confirmations.create_booking_confirmation",
    "conversation.interpret_conversation",
    "patients.create_patient",
    "vogent.vogent_book",
    "vogent.vogent_confirm_slot",
    "vogent.vogent_interpret_intent",
    "vogent.vogent_patient_lookup",
    "vogent.vogent_routing",
    "vogent.vogent_webhooks",
}


def enforce_rate_limit(app: Flask) -> None:
    if not app.config.get("RATE_LIMIT_ENABLED", True):
        return
    endpoint = (request.endpoint or "").removeprefix("api.")
    if request.method != "POST" or endpoint not in PROTECTED_ENDPOINTS:
        return

    max_requests = int(app.config.get("RATE_LIMIT_MAX_REQUESTS", 60))
    window_seconds = int(app.config.get("RATE_LIMIT_WINDOW_SECONDS", 60))
    if max_requests <= 0 or window_seconds <= 0:
        return

    route = endpoint or request.path
    identifier_hash = _identifier_hash(request)
    now = datetime.now(UTC)
    window_start = _window_start(now, window_seconds)
    bucket_key = f"{route}:{identifier_hash}:{int(window_start.timestamp())}"
    session = get_session()

    bucket = session.scalar(
        select(ApiRateLimitBucket).where(ApiRateLimitBucket.bucket_key == bucket_key).with_for_update()
    )
    if bucket is None:
        bucket = ApiRateLimitBucket(
            bucket_key=bucket_key,
            route=route,
            identifier_hash=identifier_hash,
            window_start=window_start,
            count=1,
        )
        session.add(bucket)
        try:
            session.commit()
            return
        except IntegrityError:
            session.rollback()
            bucket = session.scalar(
                select(ApiRateLimitBucket).where(ApiRateLimitBucket.bucket_key == bucket_key).with_for_update()
            )
            if bucket is None:
                raise

    if bucket.count >= max_requests:
        retry_after = max(1, int((window_start + timedelta(seconds=window_seconds) - now).total_seconds()))
        raise ApiError(
            "RATE_LIMIT_EXCEEDED",
            "Too many requests. Please retry shortly.",
            429,
            details={"retry_after_seconds": retry_after},
        )
    bucket.count += 1
    session.commit()


def _identifier_hash(current_request: Request) -> str:
    forwarded_for = current_request.headers.get("X-Forwarded-For", "")
    remote = forwarded_for.split(",", 1)[0].strip() if forwarded_for else current_request.remote_addr or "unknown"
    secret = current_request.headers.get("X-Vogent-Function-Secret", "")
    raw = f"{remote}:{secret[:8]}:{current_request.user_agent.string[:80]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _window_start(now: datetime, window_seconds: int) -> datetime:
    epoch = int(now.timestamp())
    return datetime.fromtimestamp(epoch - (epoch % window_seconds), tz=UTC)
