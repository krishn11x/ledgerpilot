"""Evaluation metrics."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from ledgerpilot.api.errors import NotFoundError
from ledgerpilot.evaluation.harness import report_to_dict, run_evaluation
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
    """Match rate, value unreconciled, break mix, aging."""
    report = run_evaluation("baseline", with_agent=False)
    return {
        "auto_match_rate": report.auto_match_rate,
        "false_positive_match_rate": report.false_positive_match_rate,
        "value_unreconciled_minor": report.value_unreconciled_minor,
    }
