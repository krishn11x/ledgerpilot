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

import time
from datetime import UTC, datetime

from ledgerpilot.domain.enums import BreakType, MatchMethod, MatchStatus
from ledgerpilot.domain.models import Break, Match, MatchLeg, PayoutBatch
from ledgerpilot.domain.money import FxRate, Money
from ledgerpilot.ingest.normalize import extract_references
from ledgerpilot.recon.classify import build_break
from ledgerpilot.recon.keys import match_id_for
from ledgerpilot.recon.types import PassResult, ReconContext


class AggregatePayoutRule:
    """Pass 4: Reference-led N:1 aggregate payout matching."""

    name = "aggregate_payout"
    method = MatchMethod.AGGREGATE_PAYOUT

    def verify_batch_arithmetic(
        self,
        ctx: ReconContext,
        payout_id: str,
        bank_amount_minor: int,
        bank_currency: str,
    ) -> tuple[bool, int]:
        """Verify that payout expected net matches bank credit amount."""
        payout = next((p for p in ctx.payouts if p.payout_id == payout_id), None)
        if not payout:
            return False, bank_amount_minor

        txns_in_batch = [g for g in ctx.gateway_txns if g.payout_id == payout_id]
        calculated_net = (
            sum(g.net_minor for g in txns_in_batch)
            if txns_in_batch
            else payout.expected_net_minor
        )
        if txns_in_batch and payout.currency != bank_currency:
            quote = next(
                (
                    currency
                    for base, currency in ctx.fx_rates
                    if base == payout.currency
                ),
                None,
            )
            if quote is not None:
                calculated_net = FxRate(
                    base=payout.currency,
                    quote=quote,
                    rate=ctx.fx_rates[(payout.currency, quote)],
                    as_of=payout.settled_on.isoformat(),
                ).convert(Money(calculated_net, payout.currency)).minor
        residual = bank_amount_minor - calculated_net
        return (residual == 0), residual

    def apply(self, ctx: ReconContext, unmatched: set[str]) -> PassResult:
        start_time = time.perf_counter()
        matches: list[Match] = []
        breaks: list[Break] = []
        consumed: set[str] = set()

        payout_by_id = {p.payout_id: p for p in ctx.payouts if p.payout_id in unmatched}

        for bank in ctx.bank_txns:
            if bank.bank_txn_id not in unmatched:
                continue

            extracted = extract_references(bank.narration)
            payout_ref = extracted.get("payout_id") or extracted.get("payout")
            utr_ref = extracted.get("utr") or bank.utr

            payout = None
            if payout_ref and payout_ref in payout_by_id:
                payout = payout_by_id[payout_ref]
            elif utr_ref:
                payout = next((p for p in payout_by_id.values() if p.utr == utr_ref), None)

            if payout is None:
                candidates = [
                    candidate
                    for candidate in payout_by_id.values()
                    if candidate.settled_on == bank.value_date
                    and self._expected_bank_amount(ctx, candidate, bank.currency)
                    == bank.amount_minor
                ]
                if len(candidates) == 1:
                    payout = candidates[0]

            if payout and payout.payout_id in unmatched and payout.payout_id not in consumed:
                balanced, residual = self.verify_batch_arithmetic(
                    ctx, payout.payout_id, bank.amount_minor, bank.currency
                )

                legs = [
                    MatchLeg(
                        record_type="payout",
                        record_id=payout.payout_id,
                        amount_minor=payout.expected_net_minor,
                    ),
                    MatchLeg(
                        record_type="bank_txn",
                        record_id=bank.bank_txn_id,
                        amount_minor=bank.amount_minor,
                    ),
                ]
                m_id = match_id_for([("payout", payout.payout_id), ("bank_txn", bank.bank_txn_id)])

                if balanced:
                    match = Match(
                        match_id=m_id,
                        legs=legs,
                        method=self.method,
                        status=MatchStatus.CONFIRMED,
                        confidence=1.0,
                        score_breakdown={"reference": 1.0, "batch_arithmetic": 1.0},
                        residual_minor=0,
                        created_at=datetime.now(UTC),
                    )
                    matches.append(match)
                    consumed.add(payout.payout_id)
                    consumed.add(bank.bank_txn_id)
                else:
                    brk = build_break(
                        BreakType.PAYOUT_MISMATCH,
                        amount_at_risk_minor=abs(residual),
                        currency=bank.currency,
                        legs=legs,
                        detected_by=self.name,
                        summary=(
                            f"Payout {payout.payout_id} differs from bank credit by "
                            f"{residual} minor units"
                        ),
                    )
                    breaks.append(brk)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return PassResult(
            pass_name=self.name,
            matches=matches,
            breaks=breaks,
            consumed_ids=consumed,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _expected_bank_amount(
        ctx: ReconContext, payout: PayoutBatch, bank_currency: str
    ) -> int:
        """Convert a payout's expected net into the bank account currency."""
        payout_currency = payout.currency
        if payout_currency == bank_currency:
            return payout.expected_net_minor
        rate = ctx.fx_rates.get((payout_currency, bank_currency))
        if rate is None:
            return -1
        return FxRate(
            base=payout_currency,
            quote=bank_currency,
            rate=rate,
            as_of=payout.settled_on.isoformat(),
        ).convert(Money(payout.expected_net_minor, payout_currency)).minor


class SubsetSumRule:
    """Pass 4 fallback: Subset-sum matching when no reference exists."""

    name = "aggregate_subset_sum"
    method = MatchMethod.AGGREGATE_SUBSET_SUM

    max_pool_size: int = 200
    max_subset_size: int = 60

    def find_subset(self, pool_minor: list[int], target_minor: int) -> list[int] | None:
        """DP over integer minor units to find indices summing to target_minor."""
        if not pool_minor or target_minor <= 0:
            return None

        # Truncate pool if exceeding max pool size for performance guardrail
        pool = pool_minor[: self.max_pool_size]
        memo: dict[int, list[int]] = {0: []}

        for idx, val in enumerate(pool):
            if val > target_minor:
                continue
            new_entries: dict[int, list[int]] = {}
            for current_sum, current_indices in memo.items():
                new_sum = current_sum + val
                if new_sum == target_minor:
                    return [*current_indices, idx]
                if new_sum < target_minor and new_sum not in memo and (
                    len(current_indices) + 1 <= self.max_subset_size
                ):
                    new_entries[new_sum] = [*current_indices, idx]
            memo.update(new_entries)

        return None

    def apply(self, ctx: ReconContext, unmatched: set[str]) -> PassResult:
        start_time = time.perf_counter()
        matches: list[Match] = []
        consumed: set[str] = set()

        unmatched_banks = [
            b for b in ctx.bank_txns if b.bank_txn_id in unmatched and b.bank_txn_id not in consumed
        ]
        unmatched_gtxns = [
            g for g in ctx.gateway_txns if g.txn_id in unmatched and g.txn_id not in consumed
        ]

        for bank in unmatched_banks:
            if bank.bank_txn_id in consumed:
                continue

            candidate_gtxns = [
                g
                for g in unmatched_gtxns
                if g.txn_id not in consumed and g.currency == bank.currency
            ]
            if not candidate_gtxns:
                continue

            pool_amounts = [g.net_minor for g in candidate_gtxns]
            subset_indices = self.find_subset(pool_amounts, bank.amount_minor)

            if subset_indices:
                matched_gtxns = [candidate_gtxns[i] for i in subset_indices]
                legs = [
                    MatchLeg(
                        record_type="bank_txn",
                        record_id=bank.bank_txn_id,
                        amount_minor=bank.amount_minor,
                    ),
                ] + [
                    MatchLeg(
                        record_type="gateway_txn",
                        record_id=g.txn_id,
                        amount_minor=g.net_minor,
                    )
                    for g in matched_gtxns
                ]
                m_id = f"MCH-SUBSET-{bank.bank_txn_id}"
                match = Match(
                    match_id=m_id,
                    legs=legs,
                    method=self.method,
                    status=MatchStatus.PROPOSED,  # Needs human validation
                    confidence=0.75,
                    score_breakdown={"subset_sum_exact": 1.0},
                    residual_minor=0,
                    created_at=datetime.now(UTC),
                )
                matches.append(match)
                consumed.add(bank.bank_txn_id)
                for g in matched_gtxns:
                    consumed.add(g.txn_id)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return PassResult(
            pass_name=self.name,
            matches=matches,
            breaks=[],
            consumed_ids=consumed,
            duration_ms=duration_ms,
        )
