"""Pass 2 -- tolerance matching. PLACEHOLDER -- signatures only.

For records with no usable reference but an unambiguous amount+date agreement.
Requires *all* of: same currency, amount within tolerance, date within window,
and exactly one candidate. The uniqueness requirement is what keeps this pass
safe -- two candidates at the same amount and date is an ambiguity, not a match.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from ledgerpilot.domain.enums import MatchMethod, MatchStatus
from ledgerpilot.domain.models import GatewayTxn, Match, MatchLeg
from ledgerpilot.recon.engine import PassResult, ReconContext
from ledgerpilot.recon.keys import match_id_for


class ToleranceRule:
    """Pass 2: Amount & date tolerance matching with uniqueness enforcement."""

    name = "tolerance"
    method = MatchMethod.TOLERANCE

    def apply(self, ctx: ReconContext, unmatched: set[str]) -> PassResult:
        start_time = time.perf_counter()
        matches: list[Match] = []
        consumed: set[str] = set()

        unmatched_orders = [
            o for o in ctx.orders if o.order_id in unmatched and o.order_id not in consumed
        ]
        unmatched_gtxns = [
            g for g in ctx.gateway_txns if g.txn_id in unmatched and g.txn_id not in consumed
        ]

        for order in unmatched_orders:
            if order.order_id in consumed:
                continue

            candidates: list[GatewayTxn] = []
            for gtxn in unmatched_gtxns:
                if gtxn.txn_id in consumed:
                    continue
                if gtxn.currency != order.currency:
                    continue
                if abs(gtxn.gross_minor - order.gross_minor) > ctx.amount_tolerance_minor:
                    continue
                delta_days = abs((gtxn.captured_at.date() - order.placed_at.date()).days)
                if delta_days > ctx.date_window_days:
                    continue
                candidates.append(gtxn)

            # Requires EXACTLY ONE candidate to avoid ambiguous pairing
            if len(candidates) == 1:
                gtxn = candidates[0]
                diff = abs(gtxn.gross_minor - order.gross_minor)
                confidence = max(0.80, 1.0 - (diff / max(order.gross_minor, 1)))

                legs = [
                    MatchLeg(
                        record_type="order",
                        record_id=order.order_id,
                        amount_minor=order.gross_minor,
                    ),
                    MatchLeg(
                        record_type="gateway_txn",
                        record_id=gtxn.txn_id,
                        amount_minor=gtxn.gross_minor,
                    ),
                ]
                m_id = match_id_for([("order", order.order_id), ("gateway_txn", gtxn.txn_id)])
                match = Match(
                    match_id=m_id,
                    legs=legs,
                    method=self.method,
                    status=MatchStatus.CONFIRMED,
                    confidence=confidence,
                    score_breakdown={"amount_diff_minor": float(diff)},
                    residual_minor=diff,
                    created_at=datetime.now(UTC),
                )
                matches.append(match)
                consumed.add(order.order_id)
                consumed.add(gtxn.txn_id)

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        return PassResult(
            pass_name=self.name,
            matches=matches,
            breaks=[],
            consumed_ids=consumed,
            duration_ms=duration_ms,
        )
