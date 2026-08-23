"""Synthetic scenarios. SKELETON -- generation returns 501, listing is real."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ledgerpilot.api.schemas import GenerateScenarioRequest
from ledgerpilot.synth.scenarios import SCENARIOS

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", summary="List available scenarios")
def list_scenarios() -> dict[str, Any]:
    """Return the named scenario catalogue. Implemented -- it is static config."""
    return {
        "items": [
            {
                "name": s.name,
                "description": s.description,
                "seed": s.seed,
                "order_count": s.order_count,
                "period_days": s.period_days,
            }
            for s in SCENARIOS.values()
        ],
        "total": len(SCENARIOS),
    }


@router.post("/generate", status_code=202, summary="Generate a synthetic dataset")
def generate(body: GenerateScenarioRequest) -> dict[str, Any]:
    """TODO(phase-6): materialise CSVs plus the ground-truth answer key."""
    raise NotImplementedError
