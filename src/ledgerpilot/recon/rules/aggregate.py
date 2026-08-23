"""Pass 4 -- aggregate N:1 payout matching. PLACEHOLDER -- signatures only.

The differentiating pass. Gateways settle in batches, so many transactions roll
into one bank credit net of fees:

    SUM(net) - SUM(refunds) +/- adjustments == bank credit

``net`` is already ``gross - fee - tax`` per transaction (see
``domain.policy.FeeSchedule``), so the batch identity sums *net* rather than
subtracting fees again at the batch level -- doing both double-counts the fee
and the GST on it.

Two strategies, in order:

  1. **Reference-led (primary).** Extract the payout id / UTR from the bank
     narration, look up the batch, verify the arithmetic. Deterministic, fast,
     and the path most real settlements take.

  2. **Subset-sum (fallback only).** When narration carries no usable
     reference, search for a subset of transactions in the date window summing
     to the credit. Exact over integer minor units via dynamic programming,
     bounded by the settlement window.

Subset-sum is a *fallback*, not the main path -- it is exponential in the worst
case and, more importantly, a subset that happens to sum correctly is not proof
of a real settlement. Any subset-sum match is capped below the auto-approve
confidence threshold so it always gets human eyes.
"""

from __future__ import annotations

from ledgerpilot.domain.enums import MatchMethod
from ledgerpilot.recon.engine import PassResult, ReconContext


class AggregatePayoutRule:
    """TODO(phase-3). Reference-led batch matching."""

    name = "aggregate_payout"
    method = MatchMethod.AGGREGATE_PAYOUT

    def apply(self, ctx: ReconContext, unmatched: set[str]) -> PassResult:
        raise NotImplementedError

    def verify_batch_arithmetic(self, payout_id: str, bank_amount_minor: int) -> tuple[bool, int]:
        """TODO: return (balanced, residual_minor).

        A non-zero residual is a PAYOUT_MISMATCH break, and the residual amount
        is itself the most useful diagnostic -- if it equals the expected fee on
        one transaction, you know exactly which record is wrong.
        """
        raise NotImplementedError


class SubsetSumRule:
    """TODO(phase-3). Fallback when no payout reference is recoverable."""

    name = "aggregate_subset_sum"
    method = MatchMethod.AGGREGATE_SUBSET_SUM

    # Guardrails: refuse rather than hang. A too-large candidate pool becomes
    # an escalation, not an unbounded search.
    max_pool_size: int = 200
    max_subset_size: int = 60

    def apply(self, ctx: ReconContext, unmatched: set[str]) -> PassResult:
        raise NotImplementedError

    def find_subset(self, pool_minor: list[int], target_minor: int) -> list[int] | None:
        """TODO: DP over integer minor units; return indices or None.

        Integer minor units are what make exact DP possible here -- with floats
        this would need epsilon comparisons and would produce wrong subsets.
        """
        raise NotImplementedError
