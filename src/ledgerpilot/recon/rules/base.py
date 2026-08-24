"""The rule contract. PLACEHOLDER -- protocol only.

Every pass is a pure function of (context, unmatched set) -> PassResult. No
rule may write to the database, mutate the context, or read the clock: those
constraints are what make the engine deterministic and replayable.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ledgerpilot.domain.enums import MatchMethod
from ledgerpilot.recon.types import PassResult, ReconContext


@runtime_checkable
class MatchRule(Protocol):
    """A single cascade pass."""

    name: str
    method: MatchMethod

    def apply(self, ctx: ReconContext, unmatched: set[str]) -> PassResult:
        """Attempt matches over ``unmatched`` only. Must not mutate ``ctx``."""
        ...
