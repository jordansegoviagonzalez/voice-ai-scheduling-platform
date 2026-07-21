from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import text

from app.extensions import get_session

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():  # type: ignore[no-untyped-def]
    session = get_session()
    session.execute(text("SELECT 1"))
    return jsonify({"status": "ok", "backend": "healthy", "database": "healthy"})
