from __future__ import annotations

import pytest

from app.config import Config, ConfigError


def test_non_test_runtime_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ConfigError, match="DATABASE_URL is required"):
        Config.from_env()


def test_non_test_runtime_rejects_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///local.db")

    with pytest.raises(ConfigError, match="SQLite is allowed only"):
        Config.from_env()


def test_test_runtime_allows_explicit_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///test.db")

    assert Config.from_env().database_url == "sqlite+pysqlite:///test.db"


def test_production_requires_postgresql_and_strong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/app")
    monkeypatch.setenv("SECRET_KEY", "dev-only-change-me")

    with pytest.raises(ConfigError, match="SECRET_KEY"):
        Config.from_env()

    monkeypatch.setenv("SECRET_KEY", "replace-with-a-long-random-value")
    with pytest.raises(ConfigError, match="SECRET_KEY"):
        Config.from_env()


def test_production_rejects_openai_test_mode_without_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db:5432/app")
    monkeypatch.setenv("SECRET_KEY", "a-long-random-production-secret")
    monkeypatch.setenv("OPENAI_INTEGRATION_MODE", "test")
    monkeypatch.delenv("ALLOW_OPENAI_TEST_MODE_IN_PRODUCTION", raising=False)

    with pytest.raises(ConfigError, match="OPENAI_INTEGRATION_MODE=test"):
        Config.from_env()
