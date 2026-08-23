"""Metric definitions. PLACEHOLDER -- signatures only.

Definitions are stated explicitly here because reconciliation metrics are easy
to define flatteringly. In particular ``auto_match_rate`` counts only matches
committed with no human involvement -- counting human-approved matches in the
"automated" number is the standard way these figures get inflated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ledgerpilot.domain.enums import BreakType


@dataclass(slots=True)
class ConfusionCounts:
    """Per-break-type confusion matrix against ground truth."""

    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0

    @property
    def precision(self) -> float:
        """TODO: tp / (tp + fp), 1.0 when nothing was predicted."""
        raise NotImplementedError

    @property
    def recall(self) -> float:
        """TODO: tp / (tp + fn), 1.0 when there was nothing to find."""
        raise NotImplementedError

    @property
    def f1(self) -> float:
        raise NotImplementedError


@dataclass(slots=True)
class EvalReport:
    """The metrics table -- the credibility artifact."""

    scenario: str
    seed: int
    total_records: int = 0

    # -- Coverage ------------------------------------------------------------
    auto_match_rate: float = 0.0
    escalation_rate: float = 0.0
    unmatched_rate: float = 0.0

    # -- Correctness ---------------------------------------------------------
    per_type: dict[BreakType, ConfusionCounts] = field(default_factory=dict)
    false_positive_match_rate: float = 0.0  # the headline number
    misclassification_rate: float = 0.0

    # -- Business framing ----------------------------------------------------
    value_unreconciled_minor: int = 0
    value_at_risk_minor: int = 0
    currency: str = "INR"

    # -- Cost ----------------------------------------------------------------
    agent_breaks_processed: int = 0
    agent_tokens_total: int = 0
    mean_tokens_per_break: float = 0.0
    wall_clock_seconds: float = 0.0

    def macro_precision(self) -> float:
        """TODO: unweighted mean precision across break types.

        Unweighted on purpose: rare break types like chargebacks matter as much
        as common ones, and a weighted average lets a good score on the frequent
        types hide total failure on the rare ones.
        """
        raise NotImplementedError

    def macro_recall(self) -> float:
        raise NotImplementedError

    def to_markdown(self) -> str:
        """TODO: render the metrics table for the README, CLI and API."""
        raise NotImplementedError


def compute_confusion(
    predicted: list[tuple[str, BreakType]],
    actual: list[tuple[str, BreakType]],
) -> dict[BreakType, ConfusionCounts]:
    """TODO: build the per-type confusion matrix from (record_id, type) pairs."""
    raise NotImplementedError


def false_positive_match_rate(
    committed_matches: list[tuple[str, str]],
    true_pairings: set[tuple[str, str]],
) -> float:
    """TODO: fraction of committed matches that are wrong. Minimise this.

    Counts only *committed* matches -- proposals a human rejected do not count,
    because the control worked.
    """
    raise NotImplementedError
