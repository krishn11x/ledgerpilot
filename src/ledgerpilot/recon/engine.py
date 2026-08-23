"""Cascade orchestrator. PLACEHOLDER -- signatures only.

The engine owns pass ordering and bookkeeping of what remains unmatched. It
knows nothing about *how* any individual pass matches; each rule is pluggable
via the ``MatchRule`` protocol in ``recon.rules.base``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ledgerpilot.domain.models import (
    BankTxn,
    Break,
    GatewayTxn,
    Match,
    MatchLeg,
    Order,
    PayoutBatch,
    ReconRun,
)
from ledgerpilot.recon.classify import (
    build_break,
    classify_unmatched_bank_txn,
    classify_unmatched_gateway_txn,
    classify_unmatched_order,
)
from ledgerpilot.recon.rules.aggregate import AggregatePayoutRule, SubsetSumRule
from ledgerpilot.recon.rules.base import MatchRule
from ledgerpilot.recon.rules.exact import ExactReferenceRule
from ledgerpilot.recon.rules.fuzzy import FuzzyScoreRule
from ledgerpilot.recon.rules.tolerance import ToleranceRule


@dataclass(slots=True)
class ReconContext:
    """Everything a pass may read. Immutable from a pass's point of view."""

    run_id: str
    orders: list[Order] = field(default_factory=list)
    gateway_txns: list[GatewayTxn] = field(default_factory=list)
    payouts: list[PayoutBatch] = field(default_factory=list)
    bank_txns: list[BankTxn] = field(default_factory=list)
    date_window_days: int = 3
    amount_tolerance_minor: int = 100
    min_fuzzy_score: float = 0.82
    min_fuzzy_margin: float = 0.05


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
        """Fraction of total records matched cleanly without human intervention."""
        total_consumed = sum(len(p.consumed_ids) for p in self.passes)
        total_records = len(self.residual_ids) + total_consumed
        if total_records == 0:
            return 1.0
        return total_consumed / total_records

class ReconEngine:
    """Cascade orchestrator for payment reconciliation."""

    def __init__(self, rules: list[MatchRule] | None = None) -> None:
        self.rules: list[MatchRule] = rules or [
            ExactReferenceRule(),
            ToleranceRule(),
            FuzzyScoreRule(),
            AggregatePayoutRule(),
            SubsetSumRule(),
        ]

    def run_pass(self, ctx: ReconContext, pass_name: str) -> PassResult:
        """Execute a single named pass over context unmatched set."""
        rule = next((r for r in self.rules if r.name == pass_name), None)
        if not rule:
            raise KeyError(f"Unknown pass name: {pass_name}")
        unmatched = self._all_record_ids(ctx)
        return rule.apply(ctx, unmatched)

    def run_context(self, ctx: ReconContext) -> ReconResult:
        """Execute full cascade over context, classify residual breaks, and return ReconResult."""
        unmatched = self._all_record_ids(ctx)
        pass_results: list[PassResult] = []

        all_matches: list[Match] = []
        all_breaks: list[Break] = []

        for rule in self.rules:
            res = rule.apply(ctx, unmatched)
            pass_results.append(res)
            all_matches.extend(res.matches)
            all_breaks.extend(res.breaks)
            unmatched.difference_update(res.consumed_ids)

        # Classify remaining unmatched records into residual breaks
        residual_breaks = self._classify_residuals(ctx, unmatched)
        all_breaks.extend(residual_breaks)

        recon_run = ReconRun(
            run_id=ctx.run_id,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            status="completed",
            autonomy_level=2,
            counts={
                "matches": len(all_matches),
                "breaks": len(all_breaks),
                "residuals": len(unmatched),
            },
        )

        return ReconResult(
            run=recon_run,
            passes=pass_results,
            residual_ids=unmatched,
        )

    def run(self, *, run_id: str) -> ReconResult:
        """Legacy stub compatibility."""
        ctx = ReconContext(run_id=run_id)
        return self.run_context(ctx)

    @staticmethod
    def _all_record_ids(ctx: ReconContext) -> set[str]:
        ids: set[str] = set()
        ids.update(o.order_id for o in ctx.orders)
        ids.update(g.txn_id for g in ctx.gateway_txns)
        ids.update(p.payout_id for p in ctx.payouts)
        ids.update(b.bank_txn_id for b in ctx.bank_txns)
        return ids

    @staticmethod
    def _classify_residuals(ctx: ReconContext, unmatched: set[str]) -> list[Break]:
        breaks: list[Break] = []

        for order in ctx.orders:
            if order.order_id in unmatched:
                b_type = classify_unmatched_order(order.order_id)
                leg = MatchLeg(
                    record_type="order",
                    record_id=order.order_id,
                    amount_minor=order.gross_minor,
                )
                breaks.append(
                    build_break(
                        b_type,
                        amount_at_risk_minor=order.gross_minor,
                        currency=order.currency,
                        legs=[leg],
                        summary=f"Order {order.order_id} missing in gateway captures",
                    )
                )

        for gtxn in ctx.gateway_txns:
            if gtxn.txn_id in unmatched:
                b_type = classify_unmatched_gateway_txn(gtxn)
                leg = MatchLeg(
                    record_type="gateway_txn",
                    record_id=gtxn.txn_id,
                    amount_minor=gtxn.gross_minor,
                )
                breaks.append(
                    build_break(
                        b_type,
                        amount_at_risk_minor=gtxn.gross_minor,
                        currency=gtxn.currency,
                        legs=[leg],
                        summary=f"Gateway transaction {gtxn.txn_id} is {b_type.value}",
                    )
                )

        for bank in ctx.bank_txns:
            if bank.bank_txn_id in unmatched:
                b_type = classify_unmatched_bank_txn(bank.bank_txn_id)
                leg = MatchLeg(
                    record_type="bank_txn",
                    record_id=bank.bank_txn_id,
                    amount_minor=bank.amount_minor,
                )
                breaks.append(
                    build_break(
                        b_type,
                        amount_at_risk_minor=bank.amount_minor,
                        currency=bank.currency,
                        legs=[leg],
                        summary=f"Unidentified bank credit {bank.bank_txn_id}",
                    )
                )

        return breaks
