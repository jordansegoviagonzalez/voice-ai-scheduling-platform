from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.extensions import get_engine, get_session_factory
from app.models import Base
from app.seed import seed_database


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Flask]:
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.2")
    monkeypatch.setenv("OPENAI_INTEGRATION_MODE", "live")
    application = create_app({"TESTING": True, "VOGENT_FUNCTION_SECRET": None})
    Base.metadata.create_all(get_engine())
    session = get_session_factory()()
    seed_database(session)
    session.commit()
    session.close()
    yield application
    Base.metadata.drop_all(get_engine())


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture()
def ids(client: FlaskClient) -> dict[str, dict[str, int]]:
    protocol = client.get("/api/v1/protocol").get_json()
    return {
        "doctors": {item["last_name"]: item["id"] for item in protocol["doctors"]},
        "locations": {item["code"]: item["id"] for item in protocol["locations"]},
    }
