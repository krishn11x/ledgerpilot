"""Pass 2 -- tolerance matching. PLACEHOLDER -- signatures only.

For records with no usable reference but an unambiguous amount+date agreement.
Requires *all* of: same currency, amount within tolerance, date within window,
and exactly one candidate. The uniqueness requirement is what keeps this pass
safe -- two candidates at the same amount and date is an ambiguity, not a match.
"""

from __future__ import annotations

from ledgerpilot.domain.enums import MatchMethod
from ledgerpilot.recon.engine import PassResult, ReconContext


class ToleranceRule:
    """TODO(phase-2)."""

    name = "tolerance"
    method = MatchMethod.TOLERANCE

    def apply(self, ctx: ReconContext, unmatched: set[str]) -> PassResult:
        raise NotImplementedError
