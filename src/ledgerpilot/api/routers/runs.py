"""Reconciliation runs. SKELETON -- endpoints return 501."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ledgerpilot.api.schemas import StartRunRequest

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", status_code=202, summary="Start a reconciliation run")
def start_run(body: StartRunRequest) -> dict[str, Any]:
    """TODO(phase-6): create a run and execute the cascade in the background."""
    raise NotImplementedError("Run execution lands in phase 6.")


@router.get("/{run_id}", summary="Run status and counts")
def get_run(run_id: str) -> dict[str, Any]:
    """TODO(phase-6): status, per-pass counts, timings, match rate."""
    raise NotImplementedError


@router.get("/{run_id}/events", summary="Live progress (SSE)")
async def stream_run_events(run_id: str) -> Any:
    """TODO(phase-6): EventSourceResponse over ``api.sse.run_progress_stream``."""
    raise NotImplementedError
