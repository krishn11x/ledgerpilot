"""FastAPI application factory.

Runnable now: ``/health`` and ``/`` respond, ``/docs`` renders, and OpenAPI is
emitted so the TypeScript client can be generated before any feature exists.
Feature routers are wired but return 501 until implemented -- the shape of the
API is agreed first, and the frontend can be built against it immediately.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ledgerpilot import __version__
from ledgerpilot.api.deps import require_auth
from ledgerpilot.api.errors import register_exception_handlers
from ledgerpilot.api.routers import audit, breaks, health, ledger, matches, metrics, runs, scenarios
from ledgerpilot.config import settings
from ledgerpilot.logging import configure_logging, get_logger
from ledgerpilot.store.db import create_all

log = get_logger(__name__)

DESCRIPTION = """
**LedgerPilot** -- AI Finance Controller for autonomous three-way payment
reconciliation.

Reconciles `Order -> Gateway Txn -> Payout Batch -> Bank Credit`.

Architecture: a deterministic matching cascade clears the bulk of volume with
no LLM involved; an agent handles only the ambiguous residual, and every agent
proposal is re-verified by code before it can affect the ledger.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown."""
    configure_logging()
    log.info(
        "api.startup",
        version=__version__,
        env=settings.env,
        dialect="postgres" if settings.is_postgres else "sqlite",
        agent_available=settings.agent_available,
        autonomy_level=int(settings.autonomy_level),
    )
    create_all()
    yield
    log.info("api.shutdown")


def create_app() -> FastAPI:
    """Build the application. Called by uvicorn and by tests."""
    app = FastAPI(
        title="LedgerPilot API",
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Operational
    app.include_router(health.router)

    # Feature routers -- skeletons, 501 until implemented
    app.include_router(runs.router, dependencies=[Depends(require_auth)])
    app.include_router(breaks.router, dependencies=[Depends(require_auth)])
    app.include_router(matches.router, dependencies=[Depends(require_auth)])
    app.include_router(ledger.router, dependencies=[Depends(require_auth)])
    app.include_router(audit.router, dependencies=[Depends(require_auth)])
    app.include_router(metrics.router, dependencies=[Depends(require_auth)])
    app.include_router(scenarios.router, dependencies=[Depends(require_auth)])

    @app.get("/", tags=["meta"], summary="Service banner")
    def root() -> dict[str, Any]:
        return {
            "service": "ledgerpilot",
            "version": __version__,
            "status": "scaffold",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    return app


app = create_app()
