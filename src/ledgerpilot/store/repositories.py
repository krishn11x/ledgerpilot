"""Repository layer: the only code that issues queries.

Repositories exist so that the reconciliation engine and the agent's tools can
be handed a narrow, typed data-access interface rather than a Session. Two
payoffs: the engine can be tested against in-memory fakes, and the agent's
tool surface can be made provably read-only by construction.

Every repository takes a ``Session`` and never opens one. Transaction control
belongs to the caller -- a repository that committed on its own behalf would
make "every write pairs with an audit event in the same transaction"
unenforceable.

Upserts are written to be **backend-portable**: no ``ON CONFLICT``, no
``INSERT ... ON DUPLICATE KEY``. Existing primary keys are read once, the batch
is partitioned into inserts and updates, and each half goes out as a single
ORM-enabled executemany. The ``IN`` clause is chunked because SQLite caps bound
parameters per statement and an 8,000-order batch would blow straight through
that limit.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from datetime import datetime
from typing import Any, Protocol, TypeVar

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import InstrumentedAttribute, Session

from ledgerpilot.domain.enums import BreakStatus, BreakType
from ledgerpilot.domain.models import (
    BankTxn,
    Break,
    GatewayTxn,
    JournalEntry,
    Match,
    Order,
    PayoutBatch,
)
from ledgerpilot.store.tables import (
    BankTxnRow,
    BreakRow,
    GatewayTxnRow,
    GroundTruthLabelRow,
    IngestRunRow,
    JournalEntryRow,
    MatchRow,
    OrderRow,
    PayoutBatchRow,
    QuarantinedRowRow,
)

#: Bound-parameter ceiling for a chunked ``IN`` clause. SQLite's historical
#: limit is 999; staying well inside it keeps the same code correct on both
#: backends without dialect sniffing.
_IN_CHUNK = 400

_T = TypeVar("_T")


def _chunks(items: Sequence[_T], size: int) -> Iterator[Sequence[_T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class ReadOnlyRepository(Protocol):
    """The surface exposed to the agent. Deliberately has no write methods.

    Making this a Protocol with no mutators means an agent tool that tries to
    write fails at type-check time, not at runtime in front of judges.
    """

    def get_order(self, order_id: str) -> Order | None: ...
    def get_gateway_txn(self, txn_id: str) -> GatewayTxn | None: ...
    def get_bank_txn(self, bank_txn_id: str) -> BankTxn | None: ...
    def get_payout(self, payout_id: str) -> PayoutBatch | None: ...

    def search_orders(
        self, *, amount_minor: int | None = None, customer_id: str | None = None
    ) -> list[Order]: ...

    def search_gateway_txns(
        self, *, order_ref: str | None = None, payout_id: str | None = None
    ) -> list[GatewayTxn]: ...

    def search_bank_txns(self, *, narration_contains: str | None = None) -> list[BankTxn]: ...


class _Repository:
    """Shared session handling and the portable upsert.

    Subclasses declare their row class, primary-key column and value mapper;
    everything else about writing is identical between them, and duplicating it
    four times is how the four tables drift apart.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    # -- Writing ------------------------------------------------------------

    def _upsert(
        self,
        row_cls: type,
        pk: InstrumentedAttribute[Any],
        mappings: list[dict[str, Any]],
        pk_name: str,
    ) -> int:
        """Insert new rows, update existing ones, return the number written.

        Idempotent by construction: re-ingesting the same file twice writes the
        same rows and leaves the row count unchanged, which is what lets a demo
        be re-run without wiping the database first.
        """
        if not mappings:
            return 0

        # Last write wins on a duplicate key inside a single batch. An
        # executemany that contained the same primary key twice would either
        # fail or silently apply in arbitrary order.
        deduped: dict[Any, dict[str, Any]] = {}
        for mapping in mappings:
            deduped[mapping[pk_name]] = mapping

        ids = list(deduped)
        existing: set[Any] = set()
        for chunk in _chunks(ids, _IN_CHUNK):
            existing.update(self.session.scalars(select(pk).where(pk.in_(chunk))).all())

        to_insert = [m for key, m in deduped.items() if key not in existing]
        to_update = [m for key, m in deduped.items() if key in existing]

        if to_insert:
            self.session.execute(insert(row_cls), to_insert)
        if to_update:
            self.session.execute(update(row_cls), to_update)

        self.session.flush()
        return len(to_insert) + len(to_update)

    # -- Reading ------------------------------------------------------------

    def _count(self, row_cls: type) -> int:
        return int(self.session.scalar(select(func.count()).select_from(row_cls)) or 0)


class OrderRepository(_Repository):
    """Orders: what was owed."""

    def bulk_upsert(self, orders: list[Order]) -> int:
        return self._upsert(
            OrderRow, OrderRow.order_id, [OrderRow.values(o) for o in orders], "order_id"
        )

    def get(self, order_id: str) -> Order | None:
        row = self.session.get(OrderRow, order_id)
        return row.to_domain() if row is not None else None

    def all(self) -> list[Order]:
        rows = self.session.scalars(select(OrderRow).order_by(OrderRow.order_id)).all()
        return [row.to_domain() for row in rows]

    def by_customer(self, customer_id: str) -> list[Order]:
        rows = self.session.scalars(
            select(OrderRow).where(OrderRow.customer_id == customer_id).order_by(OrderRow.order_id)
        ).all()
        return [row.to_domain() for row in rows]

    def count(self) -> int:
        return self._count(OrderRow)


class GatewayRepository(_Repository):
    """Gateway transactions: what was captured."""

    def bulk_upsert(self, txns: list[GatewayTxn]) -> int:
        return self._upsert(
            GatewayTxnRow, GatewayTxnRow.txn_id, [GatewayTxnRow.values(t) for t in txns], "txn_id"
        )

    def get(self, txn_id: str) -> GatewayTxn | None:
        row = self.session.get(GatewayTxnRow, txn_id)
        return row.to_domain() if row is not None else None

    def all(self) -> list[GatewayTxn]:
        rows = self.session.scalars(select(GatewayTxnRow).order_by(GatewayTxnRow.txn_id)).all()
        return [row.to_domain() for row in rows]

    def for_order(self, order_ref: str) -> list[GatewayTxn]:
        """Every capture against one order. More than one is a duplicate."""
        rows = self.session.scalars(
            select(GatewayTxnRow)
            .where(GatewayTxnRow.order_ref == order_ref)
            .order_by(GatewayTxnRow.txn_id)
        ).all()
        return [row.to_domain() for row in rows]

    def for_payout(self, payout_id: str) -> list[GatewayTxn]:
        rows = self.session.scalars(
            select(GatewayTxnRow)
            .where(GatewayTxnRow.payout_id == payout_id)
            .order_by(GatewayTxnRow.txn_id)
        ).all()
        return [row.to_domain() for row in rows]

    def unsettled(self) -> list[GatewayTxn]:
        """Captured transactions with no payout -- UNSETTLED candidates.

        Filtered on ``status`` as well as ``payout_id``: a refunded or failed
        transaction that never settled is correct, not a break, and returning
        it here would manufacture exceptions out of normal lifecycle.
        """
        rows = self.session.scalars(
            select(GatewayTxnRow)
            .where(GatewayTxnRow.payout_id.is_(None))
            .where(GatewayTxnRow.status == "captured")
            .order_by(GatewayTxnRow.txn_id)
        ).all()
        return [row.to_domain() for row in rows]

    def count(self) -> int:
        return self._count(GatewayTxnRow)


class PayoutRepository(_Repository):
    """Settlement batches: the N:1 bridge between captures and bank credits."""

    def bulk_upsert(self, payouts: list[PayoutBatch]) -> int:
        return self._upsert(
            PayoutBatchRow,
            PayoutBatchRow.payout_id,
            [PayoutBatchRow.values(p) for p in payouts],
            "payout_id",
        )

    def get(self, payout_id: str) -> PayoutBatch | None:
        row = self.session.get(PayoutBatchRow, payout_id)
        return row.to_domain() if row is not None else None

    def all(self) -> list[PayoutBatch]:
        rows = self.session.scalars(select(PayoutBatchRow).order_by(PayoutBatchRow.payout_id)).all()
        return [row.to_domain() for row in rows]

    def by_utr(self, utr: str) -> list[PayoutBatch]:
        rows = self.session.scalars(
            select(PayoutBatchRow)
            .where(PayoutBatchRow.utr == utr)
            .order_by(PayoutBatchRow.payout_id)
        ).all()
        return [row.to_domain() for row in rows]

    def count(self) -> int:
        return self._count(PayoutBatchRow)


class BankRepository(_Repository):
    """Bank statement lines: what actually arrived."""

    def bulk_upsert(self, txns: list[BankTxn]) -> int:
        return self._upsert(
            BankTxnRow,
            BankTxnRow.bank_txn_id,
            [BankTxnRow.values(t) for t in txns],
            "bank_txn_id",
        )

    def get(self, bank_txn_id: str) -> BankTxn | None:
        row = self.session.get(BankTxnRow, bank_txn_id)
        return row.to_domain() if row is not None else None

    def all(self) -> list[BankTxn]:
        rows = self.session.scalars(select(BankTxnRow).order_by(BankTxnRow.bank_txn_id)).all()
        return [row.to_domain() for row in rows]

    def by_utr(self, utr: str) -> list[BankTxn]:
        rows = self.session.scalars(
            select(BankTxnRow).where(BankTxnRow.utr == utr).order_by(BankTxnRow.bank_txn_id)
        ).all()
        return [row.to_domain() for row in rows]

    def search_narration(self, fragment: str) -> list[BankTxn]:
        """Substring search over raw narration. Case-insensitive."""
        rows = self.session.scalars(
            select(BankTxnRow)
            .where(BankTxnRow.narration.ilike(f"%{fragment}%"))
            .order_by(BankTxnRow.bank_txn_id)
        ).all()
        return [row.to_domain() for row in rows]

    def with_utr_count(self) -> int:
        """How many lines had a UTR recovered. The normalisation yield."""
        return int(
            self.session.scalar(
                select(func.count()).select_from(BankTxnRow).where(BankTxnRow.utr.is_not(None))
            )
            or 0
        )

    def count(self) -> int:
        return self._count(BankTxnRow)


# ---------------------------------------------------------------------------
# Ground truth and ingest hygiene
# ---------------------------------------------------------------------------


class GroundTruthRepository(_Repository):
    """The answer key.

    Read only by ``evaluation``. Nothing in ``recon`` or ``agent`` may query
    this -- a rule that consulted the labels would score perfectly and prove
    nothing, so the separation is the whole value of having ground truth.
    """

    def bulk_upsert(self, labels: Iterable[Any]) -> int:
        """Persist ``synth.breaks.GroundTruthLabel`` records.

        Typed loosely on purpose: importing ``synth`` from ``store`` would
        invert the layering (``synth`` sits above ``store``). The label's own
        ``as_row`` method supplies the column mapping, so the dependency points
        the right way.
        """
        mappings = [label.as_row() for label in labels]
        return self._upsert(GroundTruthLabelRow, GroundTruthLabelRow.label_id, mappings, "label_id")

    def all_rows(self) -> list[GroundTruthLabelRow]:
        return list(
            self.session.scalars(
                select(GroundTruthLabelRow).order_by(GroundTruthLabelRow.label_id)
            ).all()
        )

    def count(self) -> int:
        return self._count(GroundTruthLabelRow)

    def break_count(self) -> int:
        """Labels that describe an actual break, excluding noise markers."""
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(GroundTruthLabelRow)
                .where(GroundTruthLabelRow.break_type.is_not(None))
            )
            or 0
        )

    def counts_by_type(self) -> dict[str, int]:
        rows = self.session.execute(
            select(GroundTruthLabelRow.break_type, func.count())
            .group_by(GroundTruthLabelRow.break_type)
            .order_by(GroundTruthLabelRow.break_type)
        ).all()
        return {(str(bt) if bt is not None else "none"): int(n) for bt, n in rows}


class QuarantineRepository(_Repository):
    """Rows that failed validation. Append-only within a run."""

    def add_many(self, run_id: str, rows: Iterable[Any]) -> int:
        """Store ``ingest.validate.QuarantinedRow`` records against a run."""
        mappings = [
            {
                "run_id": run_id,
                "source": row.source,
                "row_number": row.row_number,
                "raw": row.raw,
                "reason": row.reason,
            }
            for row in rows
        ]
        if not mappings:
            return 0
        self.session.execute(insert(QuarantinedRowRow), mappings)
        self.session.flush()
        return len(mappings)

    def for_run(self, run_id: str) -> list[QuarantinedRowRow]:
        return list(
            self.session.scalars(
                select(QuarantinedRowRow)
                .where(QuarantinedRowRow.run_id == run_id)
                .order_by(QuarantinedRowRow.id)
            ).all()
        )

    def count(self) -> int:
        return self._count(QuarantinedRowRow)


class IngestRunRepository(_Repository):
    """Run headers, so a set of rows can be traced to the file that produced it."""

    def start(
        self, run_id: str, *, source_dir: str, started_at: datetime, scenario: str | None = None
    ) -> None:
        self.session.execute(
            insert(IngestRunRow),
            [
                {
                    "run_id": run_id,
                    "started_at": started_at,
                    "finished_at": None,
                    "source_dir": source_dir,
                    "scenario": scenario,
                    "status": "running",
                    "counts": {},
                }
            ],
        )
        self.session.flush()

    def finish(
        self,
        run_id: str,
        *,
        finished_at: datetime,
        counts: dict[str, int],
        status: str = "completed",
    ) -> None:
        self.session.execute(
            update(IngestRunRow),
            [
                {
                    "run_id": run_id,
                    "finished_at": finished_at,
                    "counts": counts,
                    "status": status,
                }
            ],
        )
        self.session.flush()

    def get(self, run_id: str) -> IngestRunRow | None:
        return self.session.get(IngestRunRow, run_id)

    def latest(self) -> IngestRunRow | None:
        return self.session.scalars(
            select(IngestRunRow).order_by(IngestRunRow.started_at.desc()).limit(1)
        ).first()

    def count(self) -> int:
        return self._count(IngestRunRow)


# ---------------------------------------------------------------------------
# Later phases
# ---------------------------------------------------------------------------


class MatchRepository(_Repository):
    """Writes are idempotent on the content-hashed match_id."""

    def upsert(self, match: Match) -> None:
        values = MatchRow.values(match)
        row = MatchRow(**values)
        self.session.merge(row)

    def get(self, match_id: str) -> Match | None:
        row = self.session.get(MatchRow, match_id)
        return row.to_domain() if row else None

    def for_record(self, record_type: str, record_id: str) -> list[Match]:
        statement = select(MatchRow)
        rows = self.session.scalars(statement).all()
        result: list[Match] = []
        for row in rows:
            for leg in row.legs:
                if leg.get("record_type") == record_type and leg.get("record_id") == record_id:
                    result.append(row.to_domain())
                    break
        return result

    def count(self) -> int:
        return self._count(MatchRow)


class BreakRepository(_Repository):
    """Backs the exception queue."""

    def upsert(self, brk: Break) -> None:
        values = BreakRow.values(brk)
        row = BreakRow(**values)
        self.session.merge(row)

    def get(self, break_id: str) -> Break | None:
        row = self.session.get(BreakRow, break_id)
        return row.to_domain() if row else None

    def query(
        self,
        *,
        status: BreakStatus | None = None,
        break_type: BreakType | None = None,
        min_amount_minor: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Break], int]:
        statement = select(BreakRow)
        if status is not None:
            statement = statement.where(BreakRow.status == status)
        if break_type is not None:
            statement = statement.where(BreakRow.break_type == break_type)
        if min_amount_minor is not None:
            statement = statement.where(BreakRow.amount_at_risk_minor >= min_amount_minor)

        total = len(self.session.scalars(statement).all())
        paged_statement = statement.offset(offset).limit(limit)
        rows = self.session.scalars(paged_statement).all()

        return [r.to_domain() for r in rows], total

    def count(self) -> int:
        return self._count(BreakRow)


class JournalRepository(_Repository):
    """Entries are immutable once posted; corrections reverse."""

    def propose(self, entry: JournalEntry) -> None:
        values = JournalEntryRow.values(entry)
        row = JournalEntryRow(**values)
        self.session.merge(row)

    def clearing_account_balance_minor(self) -> int:
        statement = select(JournalEntryRow)
        rows = self.session.scalars(statement).all()
        net_clearing = 0
        for r in rows:
            for line in r.lines:
                if line.get("account_code") == "1100":
                    net_clearing += (line.get("debit_minor", 0) - line.get("credit_minor", 0))
        return net_clearing
