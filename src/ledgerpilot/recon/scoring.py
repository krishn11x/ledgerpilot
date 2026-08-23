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

assert abs(sum(FEATURE_WEIGHTS.values()) - 1.0) < 1e-6, "FEATURE_WEIGHTS must sum to 1.0"


@dataclass(slots=True)
class ScoredCandidate:
    """One candidate pairing with its explainable score breakdown."""

    candidate_id: str
    total: float
    features: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def score_amount(a_minor: int, b_minor: int) -> float:
    """1.0 on exact match, decaying with relative difference."""
    if a_minor == b_minor:
        return 1.0
    denom = max(abs(a_minor), abs(b_minor), 1)
    diff = abs(a_minor - b_minor)
    return max(0.0, 1.0 - (diff / denom))


def score_date(delta_days: int, *, window_days: int) -> float:
    """1.0 same day, decaying to 0.0 at window edge."""
    abs_delta = abs(delta_days)
    if abs_delta == 0:
        return 1.0
    if window_days <= 0 or abs_delta >= window_days:
        return 0.0
    return max(0.0, 1.0 - (abs_delta / window_days))


def score_narration(normalized_narration: str, reference: str) -> float:
    """Token-set ratio normalized to 0.0..1.0."""
    if not normalized_narration or not reference:
        return 0.0
    norm_u = normalized_narration.upper().strip()
    ref_u = reference.upper().strip()
    if ref_u in norm_u or norm_u in ref_u:
        return 1.0

    tokens_norm = set(norm_u.split())
    tokens_ref = set(ref_u.split())
    if not tokens_norm or not tokens_ref:
        return 0.0
    intersection = tokens_norm.intersection(tokens_ref)
    union = tokens_norm.union(tokens_ref)
    return len(intersection) / len(union)


def combined_score(features: dict[str, float]) -> float:
    """Weighted sum using FEATURE_WEIGHTS."""
    return sum(features.get(name, 0.0) * weight for name, weight in FEATURE_WEIGHTS.items())


def pick_best(
    candidates: list[ScoredCandidate],
    *,
    min_score: float,
    min_margin: float,
) -> ScoredCandidate | None:
    """Return winner or None when below threshold OR ambiguous."""
    if not candidates:
        return None

    sorted_candidates = sorted(candidates, key=lambda c: c.total, reverse=True)
    best = sorted_candidates[0]

    if best.total < min_score:
        return None

    if len(sorted_candidates) > 1:
        runner_up = sorted_candidates[1]
        if (best.total - runner_up.total) < min_margin:
            return None

    return best
