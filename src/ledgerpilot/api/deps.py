"""Shared dependencies for route handlers.

PLACEHOLDER for the repository/auth wiring; the DB session dependency is real.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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


bearer = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    """Validate the configured demo bearer token and return its actor id."""
    from ledgerpilot.config import settings

    if credentials is None or credentials.credentials != settings.api_auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return settings.api_actor


def current_actor(actor: str = Depends(require_auth)) -> str:
    """Return the trusted actor established by authentication middleware."""
    return actor


SessionDep = Depends(db_session)
SettingsDep = Depends(app_settings)
ActorDep = Depends(current_actor)
