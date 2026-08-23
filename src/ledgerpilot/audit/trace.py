"""Evidence chain assembly for explainability. PLACEHOLDER -- signatures only.

Turns the audit log into the thing a human actually reads before clicking
Approve: a chronological, plain-language account of how the system arrived at a
conclusion, with every claim linked to a source record.

Design rule: no unexplained numbers. If the UI shows "confidence 0.87", this
module supplies the per-feature breakdown behind it. A score with no
justification is not evidence, it is a vibe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EvidenceItem:
    """One citation supporting or contradicting a conclusion."""

    kind: str  # record | computation | rule | tool_call | policy
    label: str  # human-readable, e.g. "Bank credit BK-8821"
    detail: dict[str, Any] = field(default_factory=dict)
    supports: bool = True  # False = contradicting evidence, shown too


@dataclass(slots=True)
class EvidenceChain:
    """The full explanation for one break or match."""

    subject_id: str
    conclusion: str
    confidence: float | None = None
    items: list[EvidenceItem] = field(default_factory=list)
    narrative: str = ""

    def to_markdown(self) -> str:
        """TODO: render for the API and the Break Detail screen."""
        raise NotImplementedError


def build_for_break(break_id: str) -> EvidenceChain:
    """TODO: assemble from audit events + agent steps + score breakdown.

    Must include contradicting evidence as well as supporting. Showing only the
    confirming signals is how a reviewer gets talked into a wrong approval.
    """
    raise NotImplementedError


def build_for_match(match_id: str) -> EvidenceChain:
    """TODO: which pass matched, on what features, with what score."""
    raise NotImplementedError
