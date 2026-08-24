"""Metric definitions.

These metrics are intentionally explicit so evaluation results cannot
accidentally look better than they really are.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ledgerpilot.domain.enums import BreakType


@dataclass
class ConfusionCounts:
    """Per-break-type confusion matrix against ground truth."""

    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positive + self.false_positive
        return 1.0 if denom == 0 else self.true_positive / denom

    @property
    def recall(self) -> float:
        denom = self.true_positive + self.false_negative
        return 1.0 if denom == 0 else self.true_positive / denom

    @property
    def f1(self) -> float:
        denom = self.precision + self.recall
        return 0.0 if denom == 0 else (
            2 * self.precision * self.recall / denom
        )


@dataclass
class EvalReport:
    """The evaluation metrics report.

    IMPORTANT:
    This class deliberately does NOT use slots=True because the API layer
    currently serializes the report using report.__dict__.
    """

    scenario: str
    seed: int
    total_records: int = 0

    # Coverage
    auto_match_rate: float = 0.0
    escalation_rate: float = 0.0
    unmatched_rate: float = 0.0

    # Correctness
    per_type: dict[BreakType, ConfusionCounts] = field(default_factory=dict)
    false_positive_match_rate: float = 0.0
    misclassification_rate: float = 0.0

    # Business framing
    value_unreconciled_minor: int = 0
    value_at_risk_minor: int = 0
    currency: str = "INR"

    # Cost
    agent_breaks_processed: int = 0
    agent_tokens_total: int = 0
    mean_tokens_per_break: float = 0.0
    wall_clock_seconds: float = 0.0

    def macro_precision(self) -> float:
        """Unweighted mean precision across break types."""
        if not self.per_type:
            return 1.0

        return sum(
            counts.precision
            for counts in self.per_type.values()
        ) / len(self.per_type)

    def macro_recall(self) -> float:
        """Unweighted mean recall across break types."""
        if not self.per_type:
            return 1.0

        return sum(
            counts.recall
            for counts in self.per_type.values()
        ) / len(self.per_type)

    def to_markdown(self) -> str:
        """Render the metrics table."""

        lines = [
            f"# Evaluation report: {self.scenario}",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Auto-match rate | {self.auto_match_rate:.3f} |",
            f"| Escalation rate | {self.escalation_rate:.3f} |",
            f"| Unmatched rate | {self.unmatched_rate:.3f} |",
            (
                f"| False positive match rate | "
                f"{self.false_positive_match_rate:.3f} |"
            ),
            (
                f"| Misclassification rate | "
                f"{self.misclassification_rate:.3f} |"
            ),
            f"| Macro precision | {self.macro_precision():.3f} |",
            f"| Macro recall | {self.macro_recall():.3f} |",
            (
                f"| Mean tokens / break | "
                f"{self.mean_tokens_per_break:.1f} |"
            ),
            (
                f"| Value unreconciled | "
                f"{self.value_unreconciled_minor} "
                f"{self.currency} minor |"
            ),
        ]

        return "\n".join(lines)


def compute_confusion(
    predicted: list[tuple[str, BreakType]],
    actual: list[tuple[str, BreakType]],
) -> dict[BreakType, ConfusionCounts]:
    """Build the per-type confusion matrix.

    Each record_id gets at most one actual and one predicted break type.

    Rules:
    - Same actual and predicted type -> true positive.
    - Predicted type with no matching actual type -> false positive.
    - Actual type with no matching prediction -> false negative.
    - Different actual/predicted types -> false positive + false negative.
    """

    by_type: dict[BreakType, ConfusionCounts] = {
        break_type: ConfusionCounts()
        for break_type in BreakType
    }

    actual_map = dict(actual)
    predicted_map = dict(predicted)

    record_ids = set(actual_map) | set(predicted_map)

    for record_id in record_ids:
        actual_type = actual_map.get(record_id)
        predicted_type = predicted_map.get(record_id)

        # Correct prediction.
        if (
            actual_type is not None
            and actual_type == predicted_type
        ):
            by_type[actual_type].true_positive += 1
            continue

        # Wrong or spurious prediction.
        if predicted_type is not None:
            by_type[predicted_type].false_positive += 1

        # Missed ground-truth break.
        if actual_type is not None:
            by_type[actual_type].false_negative += 1

    return by_type


def false_positive_match_rate(
    committed_matches: list[tuple[str, str]],
    true_pairings: set[tuple[str, str]],
) -> float:
    """Return the fraction of committed matches that are wrong.

    Only committed matches count. Proposals rejected by a human are therefore
    excluded because the control worked.
    """

    if not committed_matches:
        return 0.0

    wrong = sum(
        1
        for pair in committed_matches
        if tuple(sorted(pair)) not in true_pairings
    )

    return wrong / len(committed_matches)