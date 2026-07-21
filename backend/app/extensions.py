from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from flask import Flask, g
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_database(app: Flask) -> None:
    global _engine, _session_factory
    database_url = app.config["DATABASE_URL"]
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=False)

    @app.before_request
    def open_session() -> None:
        g.db = get_session_factory()()

    @app.teardown_request
    def close_session(error: BaseException | None) -> None:
        session: Session | None = g.pop("db", None)
        if session is None:
            return
        if error is not None:
            session.rollback()
        session.close()


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database has not been initialized")
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        raise RuntimeError("Database has not been initialized")
    return _session_factory


def get_session() -> Session:
    session = getattr(g, "db", None)
    if session is None:
        raise RuntimeError("No request database session")
    return session


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
