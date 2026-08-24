"""Synthetic scenarios. SKELETON -- generation returns 501, listing is real."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from ledgerpilot.api.schemas import GenerateScenarioRequest
from ledgerpilot.synth.breaks import BreakInjector
from ledgerpilot.synth.generator import SyntheticGenerator, write_dataset
from ledgerpilot.synth.scenarios import SCENARIOS, get_scenario

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
    scenario = get_scenario(body.scenario)
    generator = SyntheticGenerator(
        seed=body.seed if body.seed is not None else scenario.seed,
        period_days=scenario.period_days,
        scenario=scenario.name,
    )
    dataset = generator.generate(order_count=body.order_count or scenario.order_count)
    injector = BreakInjector(seed=body.seed if body.seed is not None else scenario.seed)
    dataset, labels = injector.inject(dataset, scenario.mix)
    written = write_dataset(dataset, Path("data") / "synthetic" / scenario.name)
    return {
        "paths": {key: str(value) for key, value in written.items()},
        "ground_truth": len(labels),
    }
