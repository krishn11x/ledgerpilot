"""Shared reconciliation dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ledgerpilot.domain.models import BankTxn, Break, GatewayTxn, Match, Order, PayoutBatch


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
    fx_rates: dict[tuple[str, str], Decimal] = field(
        default_factory=lambda: {("USD", "INR"): Decimal("83.25")}
    )


@dataclass(slots=True)
class PassResult:
    """What one cascade pass produced."""

    pass_name: str
    matches: list[Match] = field(default_factory=list)
    breaks: list[Break] = field(default_factory=list)
    consumed_ids: set[str] = field(default_factory=set)
    duration_ms: int = 0
