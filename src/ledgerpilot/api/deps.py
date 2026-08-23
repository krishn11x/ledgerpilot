"""Shared dependencies for route handlers.

PLACEHOLDER for the repository/auth wiring; the DB session dependency is real.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from ledgerpilot.config import Settings, get_settings
from ledgerpilot.store.db import get_session


def db_session() -> Iterator[Session]:
    """Per-request session. FastAPI runs sync handlers in a threadpool."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def app_settings() -> Settings:
    """Injectable settings, so tests can override policy per request."""
    return get_settings()


def current_actor() -> str:
    """TODO(phase-6): resolve the acting user for the audit log.

    Hardcoded for the hackathon. Every approval must be attributable, so this
    returns a real identity rather than None even in the stub -- an audit event
    with an anonymous actor is not an audit event.
    """
    return "demo@ledgerpilot.local"


SessionDep = Depends(db_session)
SettingsDep = Depends(app_settings)
ActorDep = Depends(current_actor)
