"""Pass 1 -- exact reference matching. PLACEHOLDER -- signatures only.

Cheapest and most certain pass, so it runs first. Joins on hard keys:

    order.order_id        <-> gateway_txn.order_ref
    gateway_txn.payout_id <-> payout_batch.payout_id
    payout_batch.utr      <-> bank_txn.utr   (extracted from narration)

Confidence is 1.0 by definition. Anything this pass claims should never need
review, which is precisely why the reference extraction feeding it has to be
conservative -- a wrong regex here produces silent, high-confidence errors.
"""

from __future__ import annotations

from ledgerpilot.domain.enums import MatchMethod
from ledgerpilot.recon.engine import PassResult, ReconContext


class ExactReferenceRule:
    """TODO(phase-2)."""

    name = "exact_reference"
    method = MatchMethod.EXACT_REFERENCE

    def apply(self, ctx: ReconContext, unmatched: set[str]) -> PassResult:
        raise NotImplementedError
