"""Pass 3 -- fuzzy scored matching. PLACEHOLDER -- signatures only.

Generates candidates via blocking, scores each on multiple features, and
accepts only when the winner clears both the score threshold and the margin
over the runner-up (see ``recon.scoring.pick_best``).

Every accepted match carries its per-feature breakdown, so the UI can show
*why* rather than just a number.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from ledgerpilot.domain.enums import MatchMethod, MatchStatus
from ledgerpilot.domain.models import Match, MatchLeg
from ledgerpilot.recon.engine import PassResult, ReconContext
from ledgerpilot.recon.scoring import (
    ScoredCandidate,
    combined_score,
    pick_best,
    score_amount,
    score_date,
    score_narration,
)


class FuzzyScoreRule:
    """Pass 3: Multi-feature fuzzy scoring pass."""

    name = "fuzzy_score"
    method = MatchMethod.FUZZY_SCORE

    def candidates_for(self, ctx: ReconContext, record_id: str) -> list[ScoredCandidate]:
        """Generate scored candidate pairings for record_id."""
        target_order = next((o for o in ctx.orders if o.order_id == record_id), None)
        if not target_order:
            return []

        candidates: list[ScoredCandidate] = []
        for gtxn in ctx.gateway_txns:
            if gtxn.currency != target_order.currency:
                continue

            s_amt = score_amount(target_order.gross_minor, gtxn.gross_minor)
            delta_days = abs((gtxn.captured_at.date() - target_order.placed_at.date()).days)
            s_date = score_date(delta_days, window_days=ctx.date_window_days)
            s_narr = score_narration(gtxn.txn_id, target_order.order_id)

            features = {
                "amount": s_amt,
                "date": s_date,
                "narration": s_narr,
                "counterparty": 1.0 if gtxn.order_ref == target_order.order_id else 0.0,
            }
            total = combined_score(features)

            candidates.append(
                ScoredCandidate(
                    candidate_id=gtxn.txn_id,
                    total=total,
                    features=features,
                    notes=[f"Amount score {s_amt:.2f}", f"Date score {s_date:.2f}"],
                )
            )
        return candidates

    def apply(self, ctx: ReconContext, unmatched: set[str]) -> PassResult:
        start_time = time.perf_counter()
        matches: list[Match] = []
        consumed: set[str] = set()

        unmatched_orders = [o for o in ctx.orders if o.order_id in unmatched]

        for order in unmatched_orders:
            if order.order_id in consumed:
                continue

            candidates = self.candidates_for(ctx, order.order_id)
            # Exclude already consumed candidates
            valid_candidates = [
                c
                for c in candidates
                if c.candidate_id in unmatched and c.candidate_id not in consumed
            ]
            best = pick_best(
                valid_candidates,
                min_score=ctx.min_fuzzy_score,
                min_margin=ctx.min_fuzzy_margin,
            )

            if best:
                gtxn = next(g for g in ctx.gateway_txns if g.txn_id == best.candidate_id)
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
                m_id = f"MCH-FUZZY-{order.order_id}-{gtxn.txn_id}"
                match = Match(
                    match_id=m_id,
                    legs=legs,
                    method=self.method,
                    status=MatchStatus.CONFIRMED,
                    confidence=best.total,
                    score_breakdown=best.features,
                    residual_minor=abs(gtxn.gross_minor - order.gross_minor),
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
