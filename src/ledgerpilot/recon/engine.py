"""Cascade orchestrator. PLACEHOLDER -- signatures only.

The engine owns pass ordering and bookkeeping of what remains unmatched. It
knows nothing about *how* any individual pass matches; each rule is pluggable
via the ``MatchRule`` protocol in ``recon.rules.base``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ledgerpilot.domain.models import Break, Match, ReconRun


@dataclass(slots=True)
class ReconContext:
    """Everything a pass may read. Immutable from a pass's point of view.

    Passing an explicit context rather than a Session keeps passes pure and
    unit-testable against in-memory fixtures.
    """

    run_id: str
    # TODO: source record collections, policy snapshot, index structures


@dataclass(slots=True)
class PassResult:
    """What one cascade pass produced."""

    pass_name: str
    matches: list[Match] = field(default_factory=list)
    breaks: list[Break] = field(default_factory=list)
    consumed_ids: set[str] = field(default_factory=set)
    duration_ms: int = 0


@dataclass(slots=True)
class ReconResult:
    """Aggregate outcome of a full run."""

    run: ReconRun
    passes: list[PassResult] = field(default_factory=list)
    residual_ids: set[str] = field(default_factory=set)

    @property
    def auto_match_rate(self) -> float:
        """TODO: fraction cleared with no human touch -- the headline metric."""
        raise NotImplementedError


class ReconEngine:
    """Runs the cascade. TODO(phase-2)."""

    def __init__(self) -> None:
        # TODO: accept repositories + policy so this is testable with fakes
        pass

    def run(self, *, run_id: str) -> ReconResult:
        """TODO: execute passes 1-4 in order, collect residuals for the agent."""
        raise NotImplementedError

    def run_pass(self, ctx: ReconContext, pass_name: str) -> PassResult:
        """TODO: execute a single named pass. Useful for the demo and for eval."""
        raise NotImplementedError
