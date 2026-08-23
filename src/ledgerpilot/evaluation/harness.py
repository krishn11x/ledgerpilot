"""Evaluation runner. PLACEHOLDER -- signatures only.

Runs a scenario end to end and scores the result against ground truth. Doubles
as the regression suite: ``clean`` must produce zero breaks, and ``baseline``
must not regress below recorded thresholds.
"""

from __future__ import annotations

from pathlib import Path

from ledgerpilot.evaluation.metrics import EvalReport

# CI thresholds. A drop below any of these fails the build.
# Deliberately asymmetric: false positives are capped an order of magnitude
# tighter than the coverage floors, because a wrong match costs far more than
# an escalation.
THRESHOLDS: dict[str, float] = {
    "min_auto_match_rate": 0.85,
    "max_false_positive_match_rate": 0.001,
    "min_macro_precision": 0.90,
    "min_macro_recall": 0.80,
}


def run_evaluation(scenario: str, *, with_agent: bool = False) -> EvalReport:
    """TODO(phase-3): generate -> ingest -> reconcile -> score.

    ``with_agent=False`` measures the deterministic engine alone, which is the
    number to quote for reproducibility. ``with_agent=True`` measures the full
    system. Reporting both makes the split between the two layers legible
    instead of a claim.
    """
    raise NotImplementedError


def compare_reports(baseline: EvalReport, candidate: EvalReport) -> str:
    """TODO: markdown diff of two runs, for PR comments."""
    raise NotImplementedError


def check_thresholds(report: EvalReport) -> tuple[bool, list[str]]:
    """TODO: return (passed, failure messages) against THRESHOLDS."""
    raise NotImplementedError


def save_report(report: EvalReport, path: Path) -> None:
    """TODO: write JSON + markdown so reports are diffable in git."""
    raise NotImplementedError
