"""Health and configuration. Fully implemented -- the scaffold's proof of life."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ledgerpilot import __version__
from ledgerpilot.api.schemas import HealthResponse
from ledgerpilot.config import settings
from ledgerpilot.logging import get_logger
from ledgerpilot.store.db import get_engine

router = APIRouter(tags=["meta"])
log = get_logger(__name__)


@router.get("/health", response_model=HealthResponse, summary="Liveness and config")
def health() -> HealthResponse:
    """Report service status plus the policy actually in force.

    Returning the autonomy level and agent availability here is deliberate:
    "which policy was this instance running under" is the first question asked
    when a reconciliation result is queried, and it should not require reading
    the config file on a server.
    """
    reachable = False
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        reachable = True
    except Exception as exc:
        log.warning("health.db_unreachable", error=str(exc))

    return HealthResponse(
        status="ok" if reachable else "degraded",
        version=__version__,
        env=settings.env,
        database="postgresql" if settings.is_postgres else "sqlite",
        database_reachable=reachable,
        agent_available=settings.agent_available,
        autonomy_level=int(settings.autonomy_level),
    )
