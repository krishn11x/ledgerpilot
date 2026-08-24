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

import time
from datetime import UTC, datetime

from ledgerpilot.domain.enums import MatchMethod, MatchStatus
from ledgerpilot.domain.models import Match, MatchLeg
from ledgerpilot.ingest.normalize import extract_references
from ledgerpilot.recon.keys import match_id_for
from ledgerpilot.recon.types import PassResult, ReconContext


class ExactReferenceRule:
    """Pass 1: Exact reference matching for high confidence matches."""

    name = "exact_reference"
    method = MatchMethod.EXACT_REFERENCE

    def apply(self, ctx: ReconContext, unmatched: set[str]) -> PassResult:
        start_time = time.perf_counter()
        matches: list[Match] = []
        consumed: set[str] = set()

        # 1. Order <-> GatewayTxn on order_id == order_ref
        order_map = {o.order_id: o for o in ctx.orders if o.order_id in unmatched}
        for g in ctx.gateway_txns:
            if g.txn_id in unmatched and g.order_ref and g.order_ref in order_map:
                o = order_map[g.order_ref]
                if o.currency == g.currency and o.gross_minor == g.gross_minor:
                    legs = [
                        MatchLeg(
                            record_type="order", record_id=o.order_id, amount_minor=o.gross_minor
                        ),
                        MatchLeg(
                            record_type="gateway_txn",
                            record_id=g.txn_id,
                            amount_minor=g.gross_minor,
                        ),
                    ]
                    m_id = match_id_for([("order", o.order_id), ("gateway_txn", g.txn_id)])
                    match = Match(
                        match_id=m_id,
                        legs=legs,
                        method=self.method,
                        status=MatchStatus.CONFIRMED,
                        confidence=1.0,
                        score_breakdown={"reference": 1.0, "amount": 1.0},
                        created_at=datetime.now(UTC),
                    )
                    matches.append(match)
                    consumed.add(o.order_id)
                    consumed.add(g.txn_id)

        # 2. PayoutBatch <-> BankTxn on UTR
        payout_map = {p.utr: p for p in ctx.payouts if p.payout_id in unmatched and p.utr}
        for b in ctx.bank_txns:
            if b.bank_txn_id in unmatched:
                utr = b.utr or extract_references(b.narration).get("utr")
                if utr and utr in payout_map:
                    p = payout_map[utr]
                    if p.payout_id in unmatched and p.currency == b.currency:
                        legs = [
                            MatchLeg(
                                record_type="payout",
                                record_id=p.payout_id,
                                amount_minor=p.expected_net_minor,
                            ),
                            MatchLeg(
                                record_type="bank_txn",
                                record_id=b.bank_txn_id,
                                amount_minor=b.amount_minor,
                            ),
                        ]
                        m_id = match_id_for([("payout", p.payout_id), ("bank_txn", b.bank_txn_id)])
                        match = Match(
                            match_id=m_id,
                            legs=legs,
                            method=self.method,
                            status=MatchStatus.CONFIRMED,
                            confidence=1.0,
                            score_breakdown={"utr": 1.0},
                            created_at=datetime.now(UTC),
                        )
                        matches.append(match)
                        consumed.add(p.payout_id)
                        consumed.add(b.bank_txn_id)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return PassResult(
            pass_name=self.name,
            matches=matches,
            breaks=[],
            consumed_ids=consumed,
            duration_ms=duration_ms,
        )
