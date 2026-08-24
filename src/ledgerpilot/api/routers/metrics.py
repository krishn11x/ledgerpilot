"""Evaluation metrics."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from ledgerpilot.api.errors import NotFoundError
from ledgerpilot.evaluation.harness import report_to_dict, run_evaluation
from ledgerpilot.store.db import session_scope
from ledgerpilot.store.repositories import BreakRepository, ReconRunRepository
from ledgerpilot.synth.scenarios import SCENARIOS

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", summary="Evaluation report vs ground truth")
def get_metrics(
    scenario: Annotated[str, Query()] = "baseline",
    with_agent: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    """Auto-match rate, per-type precision/recall, FP rate."""
    if scenario not in SCENARIOS:
        raise NotFoundError(f"unknown scenario {scenario!r}")
    report = run_evaluation(scenario, with_agent=with_agent)
    return report_to_dict(report)


@router.get("/dashboard", summary="KPI summary for the dashboard")
def dashboard() -> dict[str, Any]:
    """Legacy benchmark dashboard; current run data uses ``/metrics/current``."""
    report = run_evaluation("baseline", with_agent=False)
    return {
        "auto_match_rate": report.auto_match_rate,
        "false_positive_match_rate": report.false_positive_match_rate,
        "value_unreconciled_minor": report.value_unreconciled_minor,
    }


@router.get("/current", summary="Current reconciliation metrics")
def current(run_id: Annotated[str, Query()]) -> dict[str, Any]:
    """Return only metrics belonging to the explicitly requested run."""
    with session_scope() as session:
        run = ReconRunRepository(session).get(run_id)
        if run is None:
            raise NotFoundError(f"run {run_id!r} not found")
        breaks, _ = BreakRepository(session).query(run_id=run_id, limit=500, offset=0)

    counts = run.counts
    records_checked = sum(
        int(counts.get(source, 0))
        for source in ("orders", "gateway_txns", "payouts", "bank_txns")
    )
    matched = int(counts.get("matches", 0))
    issues = int(counts.get("breaks", len(breaks)))
    return {
        "run_id": run_id,
        "records_checked": records_checked,
        "matched": matched,
        "issues_found": issues,
        "money_needing_attention_minor": sum(item.amount_at_risk_minor for item in breaks),
        "match_rate": matched / (matched + issues) if matched + issues else 1.0,
    }
