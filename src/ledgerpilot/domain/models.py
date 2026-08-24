"""Core entity shapes.

PLACEHOLDER -- field lists are the inter-layer contract; behaviour is not
implemented yet. These are *pure* types, deliberately distinct from the
SQLAlchemy tables in ``ledgerpilot.store.tables`` and from the API response
schemas. Persistence concerns must not leak in here.

The reconciliation chain these types describe, for one INR 1,200.00 order at
the default schedule of 200 bps + INR 3.00, plus 1800 bps GST on the fee::

    Order --1:1--> GatewayTxn --N:1--> PayoutBatch --1:1--> BankTxn
     1,200.00        1,200.00 gross     SUM(net)           one statement
                    -    27.00 fee      = 1,168.14         line
                    -     4.86 GST        for a 1-txn        1,168.14
                    = 1,168.14 net        batch

The N:1 step is the interesting one: gateways settle in batches, so many
transactions roll into a single bank credit net of fees. The batch total is a
sum of *net* amounts -- fees are already deducted per transaction, so
subtracting them again at the batch level double-counts them.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ledgerpilot.domain.enums import (
    BreakSeverity,
    BreakStatus,
    BreakType,
    JournalEntryStatus,
    MatchMethod,
    MatchStatus,
    TxnDirection,
)


class _Base(BaseModel):
    """Frozen, strictly-validated base for all domain entities."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Source records -- the three ledgers being reconciled
# ---------------------------------------------------------------------------


class Order(_Base):
    """A commerce/ERP order. The system of record for what was *owed*."""

    order_id: str
    customer_id: str
    gross_minor: int
    currency: str
    placed_at: datetime
    status: str
    run_id: str | None = None
    # TODO: line items, tax breakdown, shipping, promised delivery date


class GatewayTxn(_Base):
    """A payment gateway transaction. What was *captured*.

    ``net_minor`` should equal ``gross_minor - fee_minor - tax_minor``; when it
    does not, that is a FEE_VARIANCE break.
    """

    txn_id: str
    order_ref: str | None  # None => ORPHAN_PAYMENT candidate
    gross_minor: int
    fee_minor: int
    tax_minor: int
    net_minor: int
    currency: str
    status: str  # captured | refunded | disputed | failed
    payout_id: str | None  # None => UNSETTLED candidate
    captured_at: datetime
    run_id: str | None = None
    # TODO: payment method, card last4, RRN, arn, risk score


class PayoutBatch(_Base):
    """A gateway settlement batch. Bridges N transactions to 1 bank credit."""

    payout_id: str
    expected_net_minor: int
    txn_count: int
    currency: str
    settled_on: date
    utr: str | None  # bank reference, appears in narration
    run_id: str | None = None
    # TODO: adjustments, reserve held, reserve released


class BankTxn(_Base):
    """A bank statement line. What actually *arrived*.

    ``narration`` is deliberately messy free text -- extracting the payout
    reference out of it is the one genuinely LLM-shaped subtask in the system.
    """

    bank_txn_id: str
    value_date: date
    amount_minor: int
    direction: TxnDirection
    currency: str
    narration: str
    utr: str | None = None  # populated by ingest.normalize when parseable
    run_id: str | None = None
    # TODO: balance after, branch code, instrument type


# ---------------------------------------------------------------------------
# Reconciliation outputs
# ---------------------------------------------------------------------------


class MatchLeg(_Base):
    """One side of a match: a pointer to a source record."""

    record_type: str  # order | gateway_txn | payout | bank_txn
    record_id: str
    amount_minor: int


class Match(_Base):
    """A believed correspondence between source records.

    ``match_id`` is a content hash of the sorted legs, which makes the engine
    idempotent: re-running reconciliation cannot create duplicate matches.
    """

    match_id: str
    legs: list[MatchLeg]
    method: MatchMethod
    status: MatchStatus
    confidence: float = Field(ge=0.0, le=1.0)
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    residual_minor: int = 0  # unexplained remainder, 0 for a clean match
    created_at: datetime
    run_id: str | None = None


class Break(_Base):
    """An unresolved or explained discrepancy. The unit of work in the queue."""

    break_id: str
    break_type: BreakType
    severity: BreakSeverity
    status: BreakStatus
    amount_at_risk_minor: int
    currency: str
    legs: list[MatchLeg]  # whichever records are implicated
    detected_by: str  # rule id or agent run id
    detected_at: datetime
    summary: str = ""  # one-line human-readable statement
    narrative: str | None = None  # agent's root-cause explanation
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    assignee: str | None = None
    run_id: str | None = None
    # TODO: sla_due_at, resolution_note, linked journal_entry_id


# ---------------------------------------------------------------------------
# Double-entry proposals
# ---------------------------------------------------------------------------


class JournalLine(_Base):
    """One debit or credit. Exactly one of the two amounts is non-zero."""

    account_code: str
    debit_minor: int = 0
    credit_minor: int = 0
    currency: str
    memo: str = ""


class JournalEntry(_Base):
    """A balanced double-entry posting proposed for a break.

    Invariant enforced in ``ledger.balance``: sum(debits) == sum(credits), in
    integer minor units. An unbalanced entry is an error, never a warning.
    """

    entry_id: str
    break_id: str | None
    lines: list[JournalLine]
    status: JournalEntryStatus
    posting_date: date
    rationale: str = ""
    proposed_by: str = ""
    approved_by: str | None = None
    # TODO: reversal_of, period, cost centre


# ---------------------------------------------------------------------------
# Run metadata
# ---------------------------------------------------------------------------


class ReconRun(_Base):
    """One execution of the cascade. The unit of auditability. PLACEHOLDER."""

    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str = "pending"
    autonomy_level: int = 2
    counts: dict[str, int] = Field(default_factory=dict)
    # TODO: input dataset fingerprint, policy snapshot, timing per pass
