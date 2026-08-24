"""Reconciliation runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from ledgerpilot.api.errors import NotFoundError
from ledgerpilot.api.schemas import StartRunRequest
from ledgerpilot.api.sse import run_progress_stream
from ledgerpilot.ingest.loaders import load_bank_txns, load_gateway_txns, load_orders, load_payouts
from ledgerpilot.recon.engine import ReconContext, ReconEngine
from ledgerpilot.store.db import session_scope
from ledgerpilot.store.repositories import BreakRepository, MatchRepository, ReconRunRepository
from ledgerpilot.synth.scenarios import SCENARIOS, get_scenario, materialize

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", status_code=202, summary="Start a reconciliation run")
def start_run(body: StartRunRequest) -> dict[str, Any]:
    """Create a run and execute the cascade."""
    scenario_name = body.scenario or "baseline"
    if scenario_name not in SCENARIOS:
        raise NotFoundError(f"unknown scenario {scenario_name!r}")
    scenario = get_scenario(scenario_name)
    paths = materialize(scenario_name, seed=scenario.seed)
    ctx = ReconContext(
        run_id=f"RUN-{scenario_name}-{uuid4().hex[:12]}",
        orders=load_orders(Path(paths["orders"])),
        gateway_txns=load_gateway_txns(Path(paths["gateway_txns"])),
        payouts=load_payouts(Path(paths["payouts"])),
        bank_txns=load_bank_txns(Path(paths["bank_txns"])),
    )
    result = ReconEngine().run_context(ctx)
    result.run = result.run.model_copy(
        update={
            "counts": {
                **result.run.counts,
                "orders": len(ctx.orders),
                "gateway_txns": len(ctx.gateway_txns),
                "payouts": len(ctx.payouts),
                "bank_txns": len(ctx.bank_txns),
            }
        }
    )
    with session_scope() as session:
        ReconRunRepository(session).upsert(result.run)
        match_repo = MatchRepository(session)
        break_repo = BreakRepository(session)
        for match in result.matches:
            match_repo.upsert(match)
        for brk in result.breaks:
            break_repo.upsert(brk)
    return {
        "run_id": result.run.run_id,
        "scenario": scenario_name,
        "counts": result.run.counts,
        "status": result.run.status,
    }


@router.get("/{run_id}", summary="Run status and counts")
def get_run(run_id: str) -> dict[str, Any]:
    """Status, per-pass counts, timings, match rate."""
    with session_scope() as session:
        run = ReconRunRepository(session).get(run_id)
    if run is None:
        raise NotFoundError(f"run {run_id!r} not found")
    return run.model_dump()


@router.get("/{run_id}/events", summary="Live progress (SSE)")
async def stream_run_events(run_id: str) -> Any:
    """EventSourceResponse over ``api.sse.run_progress_stream``."""
    return EventSourceResponse(run_progress_stream(run_id))
