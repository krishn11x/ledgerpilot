"""Evaluation metrics. SKELETON -- endpoints return 501."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from ledgerpilot.evaluation.harness import run_evaluation

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", summary="Evaluation report vs ground truth")
def get_metrics(
    scenario: Annotated[str, Query()] = "baseline",
    with_agent: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    """TODO(phase-7): auto-match rate, per-type precision/recall, FP rate.

    Reports engine-only and engine-plus-agent separately, so the contribution
    of each layer is legible rather than asserted.
    """
    report = run_evaluation(scenario, with_agent=with_agent)
    return report.__dict__


@router.get("/dashboard", summary="KPI summary for the dashboard")
def dashboard() -> dict[str, Any]:
    """TODO(phase-8): match rate, value unreconciled, break mix, aging."""
    report = run_evaluation("baseline", with_agent=False)
    return {
        "auto_match_rate": report.auto_match_rate,
        "false_positive_match_rate": report.false_positive_match_rate,
        "value_unreconciled_minor": report.value_unreconciled_minor,
    }
