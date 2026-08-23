"""Evaluation metrics. SKELETON -- endpoints return 501."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

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
    raise NotImplementedError


@router.get("/dashboard", summary="KPI summary for the dashboard")
def dashboard() -> dict[str, Any]:
    """TODO(phase-8): match rate, value unreconciled, break mix, aging."""
    raise NotImplementedError
