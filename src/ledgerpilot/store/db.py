"""Engine and session management.

The only place in the codebase that knows how to open a database connection.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ledgerpilot.config import settings
from ledgerpilot.logging import get_logger

log = get_logger(__name__)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Build (once) the process-wide engine.

    SQLite and PostgreSQL need different pool arguments, so branch here and
    nowhere else.
    """
    url = settings.database_url
    kwargs: dict[str, object] = {"echo": settings.db_echo, "future": True}

    if url.startswith("sqlite"):
        # Make sure ./data exists before SQLite tries to create the file.
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        elif ":///" in url:
            db_path = Path(url.split(":///", 1)[1])
            db_path.parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_pool_size * 2
        kwargs["pool_pre_ping"] = True

    engine = create_engine(url, **kwargs)

    if url.startswith("sqlite"):
        _enable_sqlite_pragmas(engine)

    log.info("db.engine.created", dialect=engine.dialect.name)
    return engine


def _enable_sqlite_pragmas(engine: Engine) -> None:
    """Bring SQLite closer to PostgreSQL semantics.

    Foreign keys are OFF by default in SQLite, which would let local dev
    accept data that PostgreSQL rejects. WAL improves concurrent reads.
    """

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


@lru_cache(maxsize=1)
def _get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def get_session() -> Session:
    """Return a new session. Caller owns closing it."""
    return _get_sessionmaker()()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on any exception."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all() -> None:
    """Create tables directly from metadata.

    Convenience for tests and first-run local dev only. Alembic migrations are
    the source of truth for any real environment.
    """
    from ledgerpilot.store import tables  # noqa: F401  (registers mappers)
    from ledgerpilot.store.base import Base

    Base.metadata.create_all(bind=get_engine())
    log.info("db.schema.created", tables=len(Base.metadata.tables))
