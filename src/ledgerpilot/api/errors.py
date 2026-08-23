"""Uniform error envelope.

One response shape for every failure, so the frontend has a single error path
to handle. ``NotImplementedError`` maps to 501, which is what makes the current
scaffold honest: unbuilt endpoints say so explicitly rather than returning empty
success payloads that look like working features.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from ledgerpilot.logging import get_logger

log = get_logger(__name__)


class LedgerPilotError(Exception):
    """Base class for domain errors that map to a 4xx."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "ledgerpilot_error"


class NotFoundError(LedgerPilotError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class PolicyViolationError(LedgerPilotError):
    """An action the autonomy policy forbids, e.g. approving above materiality."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "policy_violation"


class ConflictError(LedgerPilotError):
    """Concurrent modification, e.g. two people deciding the same break."""

    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


def _envelope(code: str, message: str, detail: object = None) -> dict[str, object]:
    return {"error": {"code": code, "message": message, "detail": detail}}


def register_exception_handlers(app: FastAPI) -> None:
    """Install handlers on the app."""

    @app.exception_handler(LedgerPilotError)
    async def _domain_error(_r: Request, exc: LedgerPilotError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, str(exc)),
        )

    @app.exception_handler(NotImplementedError)
    async def _not_implemented(request: Request, exc: NotImplementedError) -> JSONResponse:
        log.info("api.not_implemented", path=request.url.path)
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content=_envelope(
                "not_implemented",
                str(exc) or "This endpoint is scaffolded but not implemented yet.",
                {"path": request.url.path},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.error("api.unhandled", path=request.url.path, error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("internal_error", "An unexpected error occurred."),
        )
