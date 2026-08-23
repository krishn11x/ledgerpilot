"""Named, reproducible datasets. PLACEHOLDER -- signatures only.

Scenarios pair a seed with a BreakMix under a name, which gives two things:
repeatable demos (the same story every run, so it can be rehearsed) and
regression tests (a match-rate drop on ``baseline`` fails CI).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ledgerpilot.config import SYNTHETIC_DIR
from ledgerpilot.synth.breaks import BreakInjector, BreakMix
from ledgerpilot.synth.generator import SyntheticGenerator, write_dataset


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    description: str
    seed: int
    order_count: int
    period_days: int
    mix: BreakMix


SCENARIOS: dict[str, Scenario] = {
    "smoke": Scenario(
        name="smoke",
        description="Tiny dataset for tests. Runs in under a second.",
        seed=1,
        order_count=50,
        period_days=7,
        mix=BreakMix(),
    ),
    "clean": Scenario(
        name="clean",
        description="No breaks at all. Any break found is a false positive.",
        seed=7,
        order_count=1_000,
        period_days=30,
        mix=BreakMix(
            missing_in_gateway=0.0,
            orphan_payment=0.0,
            amount_mismatch=0.0,
            short_payment=0.0,
            fee_variance=0.0,
            unsettled=0.0,
            payout_mismatch=0.0,
            duplicate_payment=0.0,
            refund_unapplied=0.0,
            chargeback=0.0,
            fx_variance=0.0,
            unidentified_credit=0.0,
            timing_straddle=0.0,
            narration_noise=0.0,
        ),
    ),
    "baseline": Scenario(
        name="baseline",
        description="Realistic default. The demo dataset and the CI benchmark.",
        seed=42,
        order_count=8_000,
        period_days=30,
        mix=BreakMix(),
    ),
    "messy": Scenario(
        name="messy",
        description="Heavy narration corruption. Stresses reference extraction "
        "and forces the subset-sum fallback and the agent's parser.",
        seed=99,
        order_count=5_000,
        period_days=30,
        mix=BreakMix(narration_noise=0.75, payout_mismatch=0.04),
    ),
    "adversarial": Scenario(
        name="adversarial",
        description="Many near-identical amounts on the same day, so ambiguous "
        "candidates are common. Tests whether the margin check escalates "
        "instead of guessing -- the false-positive stress case.",
        seed=1337,
        order_count=3_000,
        period_days=14,
        mix=BreakMix(duplicate_payment=0.05, amount_mismatch=0.06),
    ),
}


def get_scenario(name: str) -> Scenario:
    """Lookup a named scenario with a helpful error listing valid names."""
    if name not in SCENARIOS:
        valid = ", ".join(sorted(SCENARIOS.keys()))
        raise KeyError(f"Unknown scenario {name!r}. Valid scenarios are: {valid}")
    return SCENARIOS[name]


def materialize(
    name: str,
    *,
    seed: int | None = None,
    out_dir: Path | None = None,
) -> dict[str, str]:
    """Generate synthetic data, inject breaks, write CSVs + ground truth JSON, and return paths."""
    scenario = get_scenario(name)
    used_seed = scenario.seed if seed is None else seed
    target_dir = out_dir if out_dir is not None else (SYNTHETIC_DIR / scenario.name)

    generator = SyntheticGenerator(
        seed=used_seed,
        period_days=scenario.period_days,
        scenario=scenario.name,
    )
    clean_ds = generator.generate(order_count=scenario.order_count)

    injector = BreakInjector(seed=used_seed)
    mutated_ds, labels = injector.inject(clean_ds, scenario.mix)

    written = write_dataset(mutated_ds, target_dir)

    gt_path = target_dir / "ground_truth.json"
    gt_rows = [label.to_json_dict() for label in labels]
    gt_path.write_text(json.dumps(gt_rows, indent=2) + "\n", encoding="utf-8")
    written["ground_truth"] = gt_path

    return {k: str(v) for k, v in written.items()}
