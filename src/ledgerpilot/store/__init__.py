"""Persistence layer. PostgreSQL-ready, SQLite for zero-setup local dev.

Everything here is written against portable SQLAlchemy 2.0 constructs so that
moving from SQLite to PostgreSQL is a ``DATABASE_URL`` change and nothing else.
Postgres-specific types (JSONB, ARRAY) are avoided in favour of ``JSON`` and
child tables.

The engine is **synchronous** by design. Reconciliation is batch analytical
work, not a high-concurrency request path, and sync SQLAlchemy is markedly
simpler to reason about and to migrate with Alembic. FastAPI runs sync route
handlers in a threadpool, so this costs nothing at the API layer.
"""

from ledgerpilot.store.base import Base
from ledgerpilot.store.db import get_engine, get_session, session_scope

__all__ = ["Base", "get_engine", "get_session", "session_scope"]
