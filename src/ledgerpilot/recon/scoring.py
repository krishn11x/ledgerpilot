"""Multi-feature match scoring. PLACEHOLDER -- signatures only.

Scores are explainable by construction: every candidate produces a per-feature
breakdown that is stored on the match and rendered in the UI. "Confidence
0.87" is not useful on its own; "amount exact, date 1 day off, narration 0.79
similar" is what a controller can actually approve.

The critical guard is the **margin check**. A threshold alone is not enough --
if the top two candidates score within ``fuzzy_min_margin`` of each other, the
situation is ambiguous and must escalate rather than pick. Confidently
mis-matching is worse than escalating.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Feature weights. Must sum to 1.0; asserted at import time once implemented.
FEATURE_WEIGHTS: dict[str, float] = {
    "amount": 0.45,
    "date": 0.20,
    "narration": 0.25,
    "counterparty": 0.10,
}


@dataclass(slots=True)
class ScoredCandidate:
    """One candidate pairing with its explainable score breakdown."""

    candidate_id: str
    total: float
    features: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def score_amount(a_minor: int, b_minor: int) -> float:
    """TODO: 1.0 on exact, decaying with relative difference."""
    raise NotImplementedError


def score_date(delta_days: int, *, window_days: int) -> float:
    """TODO: 1.0 same day, decaying to 0.0 at the window edge."""
    raise NotImplementedError


def score_narration(normalized_narration: str, reference: str) -> float:
    """TODO: RapidFuzz token-set ratio, normalised to 0..1."""
    raise NotImplementedError


def combined_score(features: dict[str, float]) -> float:
    """TODO: weighted sum using FEATURE_WEIGHTS."""
    raise NotImplementedError


def pick_best(
    candidates: list[ScoredCandidate],
    *,
    min_score: float,
    min_margin: float,
) -> ScoredCandidate | None:
    """TODO: return the winner, or None when below threshold OR ambiguous.

    Returning None on ambiguity is the point of this function -- that None is
    what routes the case to the agent and then to a human.
    """
    raise NotImplementedError
