"""ORM table definitions.

Phase 1 lands the source-record tables plus the three tables that make an
ingest run auditable: the ground-truth answer key, the quarantine, and the run
header itself.

    Source data     orders, gateway_txns, payout_batches, bank_txns
    Answer key      ground_truth_labels
    Ingest hygiene  quarantined_rows, ingest_runs

Later phases add matches / breaks / recon_runs (phase 2), accounts and
journal entries (phase 4), and the hash-chained audit log (phase 5).

**The four source tables carry no foreign keys to each other, on purpose.**
A dangling reference is not corruption here, it is the signal: an
``ORPHAN_PAYMENT`` *is* a gateway transaction whose ``order_ref`` points at no
order, and an ``UNSETTLED`` transaction *is* one whose ``payout_id`` points
nowhere. Declaring those columns as foreign keys would make a genuinely broken
dataset impossible to load, which would defeat the entire product. Referential
integrity between ledgers is what reconciliation *measures*; it is not
something the schema may assume. Foreign keys appear only where the
relationship is internal bookkeeping (``quarantined_rows`` -> ``ingest_runs``).

Portability rules observed throughout:
  * ``JSON`` not ``JSONB``; ``Enum(native_enum=False)`` with an explicit name
    so the emitted CHECK constraint is stable and droppable
  * ``values_callable`` on every enum, so the lowercase *value* is stored
    rather than SQLAlchemy's default of the member *name* -- the enum values
    are the cross-layer contract (see ``domain.enums``)
  * money as ``BigInteger`` minor units -- never Float, never Numeric
  * ``DateTime(timezone=True)`` everywhere; UTC in, UTC out
  * every constraint named via the base naming convention
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ledgerpilot.domain.enums import (
    BreakType,
    ExpectedOutcome,
    ResolutionCategory,
    TxnDirection,
)
from ledgerpilot.domain.models import BankTxn, GatewayTxn, Order, PayoutBatch
from ledgerpilot.store.base import Base, TimestampMixin

__all__ = [
    "BankTxnRow",
    "Base",
    "GatewayTxnRow",
    "GroundTruthLabelRow",
    "IngestRunRow",
    "OrderRow",
    "PayoutBatchRow",
    "QuarantinedRowRow",
    "TimestampMixin",
]


def _enum_column(enum_cls: type, *, name: str) -> Enum:
    """A portable, value-storing enum column.

    Two non-default arguments, both load-bearing. ``native_enum=False`` renders
    a VARCHAR plus a named CHECK constraint, which SQLite can create and
    Alembic can drop. ``values_callable`` makes SQLAlchemy store ``"credit"``
    instead of ``"CREDIT"``: the enum *values* are what the JSON API, the SQL
    and the frontend all agree on, so storing the member name would put the
    database out of step with every other layer.
    """
    return Enum(
        enum_cls,
        native_enum=False,
        name=name,
        length=48,
        values_callable=lambda e: [member.value for member in e],
    )


def _as_utc(value: datetime) -> datetime:
    """Re-attach UTC to a datetime that came back from the database naive.

    SQLite has no timezone type, so ``DateTime(timezone=True)`` round-trips as
    a naive value there while PostgreSQL returns it aware. Normalising on read
    means a record loaded from either backend compares equal to the record that
    was written, which is what makes the round-trip test meaningful rather than
    backend-specific.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# Source records -- the four ledgers being reconciled
# ---------------------------------------------------------------------------


class OrderRow(Base, TimestampMixin):
    """Commerce/ERP orders: the system of record for what was owed."""

    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    gross_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    @classmethod
    def from_domain(cls, record: Order) -> OrderRow:
        return cls(
            order_id=record.order_id,
            customer_id=record.customer_id,
            gross_minor=record.gross_minor,
            currency=record.currency,
            placed_at=record.placed_at,
            status=record.status,
        )

    @staticmethod
    def values(record: Order) -> dict[str, Any]:
        """Column mapping for bulk insert/update, bypassing ORM instantiation."""
        return {
            "order_id": record.order_id,
            "customer_id": record.customer_id,
            "gross_minor": record.gross_minor,
            "currency": record.currency,
            "placed_at": record.placed_at,
            "status": record.status,
        }

    def to_domain(self) -> Order:
        return Order(
            order_id=self.order_id,
            customer_id=self.customer_id,
            gross_minor=self.gross_minor,
            currency=self.currency,
            placed_at=_as_utc(self.placed_at),
            status=self.status,
        )


class GatewayTxnRow(Base, TimestampMixin):
    """Payment gateway transactions: what was captured.

    ``order_ref`` and ``payout_id`` are plain indexed strings, not foreign
    keys. See the module docstring -- a reference that points nowhere is the
    break, not a violation.
    """

    __tablename__ = "gateway_txns"

    txn_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_ref: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    gross_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fee_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    net_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payout_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    @classmethod
    def from_domain(cls, record: GatewayTxn) -> GatewayTxnRow:
        return cls(**cls.values(record))

    @staticmethod
    def values(record: GatewayTxn) -> dict[str, Any]:
        return {
            "txn_id": record.txn_id,
            "order_ref": record.order_ref,
            "gross_minor": record.gross_minor,
            "fee_minor": record.fee_minor,
            "tax_minor": record.tax_minor,
            "net_minor": record.net_minor,
            "currency": record.currency,
            "status": record.status,
            "payout_id": record.payout_id,
            "captured_at": record.captured_at,
        }

    def to_domain(self) -> GatewayTxn:
        return GatewayTxn(
            txn_id=self.txn_id,
            order_ref=self.order_ref,
            gross_minor=self.gross_minor,
            fee_minor=self.fee_minor,
            tax_minor=self.tax_minor,
            net_minor=self.net_minor,
            currency=self.currency,
            status=self.status,
            payout_id=self.payout_id,
            captured_at=_as_utc(self.captured_at),
        )


class PayoutBatchRow(Base, TimestampMixin):
    """Gateway settlement batches: the N:1 bridge to a bank credit."""

    __tablename__ = "payout_batches"

    payout_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    expected_net_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    txn_count: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    settled_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    utr: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    @classmethod
    def from_domain(cls, record: PayoutBatch) -> PayoutBatchRow:
        return cls(**cls.values(record))

    @staticmethod
    def values(record: PayoutBatch) -> dict[str, Any]:
        return {
            "payout_id": record.payout_id,
            "expected_net_minor": record.expected_net_minor,
            "txn_count": record.txn_count,
            "currency": record.currency,
            "settled_on": record.settled_on,
            "utr": record.utr,
        }

    def to_domain(self) -> PayoutBatch:
        return PayoutBatch(
            payout_id=self.payout_id,
            expected_net_minor=self.expected_net_minor,
            txn_count=self.txn_count,
            currency=self.currency,
            settled_on=self.settled_on,
            utr=self.utr,
        )


class BankTxnRow(Base, TimestampMixin):
    """Bank statement lines: what actually arrived.

    ``narration`` is ``Text`` and stored verbatim -- it is evidence, and the
    audit trail has to be able to show exactly what the bank sent. ``utr`` is
    the *derived* column, populated by ``ingest.normalize`` when it can be
    parsed out of the narration; nullable because for some vendor formats it
    genuinely cannot be.
    """

    __tablename__ = "bank_txns"

    bank_txn_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    direction: Mapped[TxnDirection] = mapped_column(
        _enum_column(TxnDirection, name="txn_direction"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    narration: Mapped[str] = mapped_column(Text, nullable=False)
    utr: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    @classmethod
    def from_domain(cls, record: BankTxn) -> BankTxnRow:
        return cls(**cls.values(record))

    @staticmethod
    def values(record: BankTxn) -> dict[str, Any]:
        return {
            "bank_txn_id": record.bank_txn_id,
            "value_date": record.value_date,
            "amount_minor": record.amount_minor,
            "direction": record.direction,
            "currency": record.currency,
            "narration": record.narration,
            "utr": record.utr,
        }

    def to_domain(self) -> BankTxn:
        return BankTxn(
            bank_txn_id=self.bank_txn_id,
            value_date=self.value_date,
            amount_minor=self.amount_minor,
            direction=self.direction,
            currency=self.currency,
            narration=self.narration,
            utr=self.utr,
        )


# ---------------------------------------------------------------------------
# The answer key
# ---------------------------------------------------------------------------


class GroundTruthLabelRow(Base, TimestampMixin):
    """One injected break and the outcome a correct system should reach.

    Persisted next to the data it describes so a metrics table can be tied
    back to the exact dataset that produced it.

    ``break_type`` is nullable: the narration-noise injector degrades a record
    without creating a break, and recording that as ``UNCLASSIFIED`` would
    inflate the break count with cases that have nothing to find. A null
    ``break_type`` means "I changed this record, and the correct answer is
    still a clean match".

    Nothing in the reconciliation engine may read this table. It is written by
    ``synth`` and read only by ``evaluation``; a rule that consulted the answer
    key would score perfectly and measure nothing.
    """

    __tablename__ = "ground_truth_labels"

    label_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    break_type: Mapped[BreakType | None] = mapped_column(
        _enum_column(BreakType, name="break_type"), nullable=True, index=True
    )
    expected_outcome: Mapped[ExpectedOutcome] = mapped_column(
        _enum_column(ExpectedOutcome, name="expected_outcome"), nullable=False
    )
    resolution_category: Mapped[ResolutionCategory] = mapped_column(
        _enum_column(ResolutionCategory, name="resolution_category"), nullable=False
    )
    affected_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    amount_at_risk_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    injector: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    detail: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)


# ---------------------------------------------------------------------------
# Ingest hygiene
# ---------------------------------------------------------------------------


class IngestRunRow(Base):
    """Header for one ingest execution.

    Deliberately without ``TimestampMixin``: this table owns its own lifecycle
    timestamps, and a second near-identical pair of columns would be noise.
    """

    __tablename__ = "ingest_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_dir: Mapped[str] = mapped_column(Text, nullable=False)
    scenario: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    counts: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)


class QuarantinedRowRow(Base, TimestampMixin):
    """A source row that failed validation, kept with its reason.

    The whole point of this table is that malformed input is *visible*. A row
    that cannot be parsed is never dropped and never fatal: it lands here with
    its original contents and a reason, and it shows up in the run summary.
    Silent data loss in a financial control is worse than a loud failure.
    """

    __tablename__ = "quarantined_rows"
    __table_args__ = (Index("ix_quarantined_rows_run_source", "run_id", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ingest_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
