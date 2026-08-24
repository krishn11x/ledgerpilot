"""Repository layer: the only code that issues queries.

Repositories expose narrow, typed data-access interfaces instead of leaking
SQLAlchemy Sessions into domain, reconciliation, or agent logic.

Transaction ownership stays with the caller. Repositories never commit on
their own, which allows business changes and their audit events to be committed
atomically.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from datetime import datetime
from typing import Any, Protocol, TypeVar

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import InstrumentedAttribute, Session

from ledgerpilot.audit.events import AuditAction, AuditEvent
from ledgerpilot.domain.enums import (
    BreakStatus,
    BreakType,
    DecisionActor,
    JournalEntryStatus,
)
from ledgerpilot.domain.models import (
    BankTxn,
    Break,
    GatewayTxn,
    JournalEntry,
    Match,
    Order,
    PayoutBatch,
    ReconRun,
)
from ledgerpilot.store.tables import (
    AuditEventRow,
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
    ReconRunRow,
)

_IN_CHUNK = 400
_T = TypeVar("_T")


def _chunks(
    items: Sequence[_T],
    size: int,
) -> Iterator[Sequence[_T]]:
    """Yield fixed-size chunks for bounded IN clauses."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


class ReadOnlyRepository(Protocol):
    """Read-only interface exposed to the agent."""

    def get_order(self, order_id: str) -> Order | None: ...

    def get_gateway_txn(self, txn_id: str) -> GatewayTxn | None: ...

    def get_bank_txn(self, bank_txn_id: str) -> BankTxn | None: ...

    def get_payout(self, payout_id: str) -> PayoutBatch | None: ...

    def search_orders(
        self,
        *,
        amount_minor: int | None = None,
        customer_id: str | None = None,
    ) -> list[Order]: ...

    def search_gateway_txns(
        self,
        *,
        order_ref: str | None = None,
        payout_id: str | None = None,
    ) -> list[GatewayTxn]: ...

    def search_bank_txns(
        self,
        *,
        narration_contains: str | None = None,
    ) -> list[BankTxn]: ...


class _Repository:
    """Shared session handling and portable upsert behavior."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _upsert(
        self,
        row_cls: type,
        pk: InstrumentedAttribute[Any],
        mappings: list[dict[str, Any]],
        pk_name: str,
    ) -> int:
        """Insert new rows and update existing rows idempotently."""
        if not mappings:
            return 0

        deduped: dict[Any, dict[str, Any]] = {}
        for mapping in mappings:
            deduped[mapping[pk_name]] = mapping

        ids = list(deduped)
        existing: set[Any] = set()

        for chunk in _chunks(ids, _IN_CHUNK):
            existing.update(
                self.session.scalars(
                    select(pk).where(pk.in_(chunk))
                ).all()
            )

        to_insert = [
            mapping
            for key, mapping in deduped.items()
            if key not in existing
        ]

        to_update = [
            mapping
            for key, mapping in deduped.items()
            if key in existing
        ]

        if to_insert:
            self.session.execute(insert(row_cls), to_insert)

        if to_update:
            self.session.execute(update(row_cls), to_update)

        self.session.flush()
        return len(to_insert) + len(to_update)

    def _count(self, row_cls: type) -> int:
        return int(
            self.session.scalar(
                select(func.count()).select_from(row_cls)
            )
            or 0
        )


class OrderRepository(_Repository):
    """Orders: what was owed."""

    def bulk_upsert(self, orders: list[Order]) -> int:
        return self._upsert(
            OrderRow,
            OrderRow.order_id,
            [OrderRow.values(order) for order in orders],
            "order_id",
        )

    def get(self, order_id: str) -> Order | None:
        row = self.session.get(OrderRow, order_id)
        return row.to_domain() if row is not None else None

    def all(self) -> list[Order]:
        rows = self.session.scalars(
            select(OrderRow).order_by(OrderRow.order_id)
        ).all()
        return [row.to_domain() for row in rows]

    def by_customer(self, customer_id: str) -> list[Order]:
        rows = self.session.scalars(
            select(OrderRow)
            .where(OrderRow.customer_id == customer_id)
            .order_by(OrderRow.order_id)
        ).all()
        return [row.to_domain() for row in rows]

    def count(self) -> int:
        return self._count(OrderRow)


class GatewayRepository(_Repository):
    """Gateway transactions: what was captured."""

    def bulk_upsert(self, txns: list[GatewayTxn]) -> int:
        return self._upsert(
            GatewayTxnRow,
            GatewayTxnRow.txn_id,
            [GatewayTxnRow.values(txn) for txn in txns],
            "txn_id",
        )

    def get(self, txn_id: str) -> GatewayTxn | None:
        row = self.session.get(GatewayTxnRow, txn_id)
        return row.to_domain() if row is not None else None

    def all(self) -> list[GatewayTxn]:
        rows = self.session.scalars(
            select(GatewayTxnRow).order_by(GatewayTxnRow.txn_id)
        ).all()
        return [row.to_domain() for row in rows]

    def for_order(self, order_ref: str) -> list[GatewayTxn]:
        """Every capture against one order."""
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
        """Captured transactions with no payout."""
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
    """Settlement batches: the N:1 bridge to bank credits."""

    def bulk_upsert(self, payouts: list[PayoutBatch]) -> int:
        return self._upsert(
            PayoutBatchRow,
            PayoutBatchRow.payout_id,
            [PayoutBatchRow.values(payout) for payout in payouts],
            "payout_id",
        )

    def get(self, payout_id: str) -> PayoutBatch | None:
        row = self.session.get(PayoutBatchRow, payout_id)
        return row.to_domain() if row is not None else None

    def all(self) -> list[PayoutBatch]:
        rows = self.session.scalars(
            select(PayoutBatchRow).order_by(PayoutBatchRow.payout_id)
        ).all()
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
            [BankTxnRow.values(txn) for txn in txns],
            "bank_txn_id",
        )

    def get(self, bank_txn_id: str) -> BankTxn | None:
        row = self.session.get(BankTxnRow, bank_txn_id)
        return row.to_domain() if row is not None else None

    def all(self) -> list[BankTxn]:
        rows = self.session.scalars(
            select(BankTxnRow).order_by(BankTxnRow.bank_txn_id)
        ).all()
        return [row.to_domain() for row in rows]

    def by_utr(self, utr: str) -> list[BankTxn]:
        rows = self.session.scalars(
            select(BankTxnRow)
            .where(BankTxnRow.utr == utr)
            .order_by(BankTxnRow.bank_txn_id)
        ).all()
        return [row.to_domain() for row in rows]

    def search_narration(self, fragment: str) -> list[BankTxn]:
        rows = self.session.scalars(
            select(BankTxnRow)
            .where(BankTxnRow.narration.ilike(f"%{fragment}%"))
            .order_by(BankTxnRow.bank_txn_id)
        ).all()
        return [row.to_domain() for row in rows]

    def with_utr_count(self) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(BankTxnRow)
                .where(BankTxnRow.utr.is_not(None))
            )
            or 0
        )

    def count(self) -> int:
        return self._count(BankTxnRow)


class GroundTruthRepository(_Repository):
    """Ground-truth answer key for evaluation only."""

    def bulk_upsert(self, labels: Iterable[Any]) -> int:
        mappings = [label.as_row() for label in labels]
        return self._upsert(
            GroundTruthLabelRow,
            GroundTruthLabelRow.label_id,
            mappings,
            "label_id",
        )

    def all_rows(self) -> list[GroundTruthLabelRow]:
        return list(
            self.session.scalars(
                select(GroundTruthLabelRow)
                .order_by(GroundTruthLabelRow.label_id)
            ).all()
        )

    def count(self) -> int:
        return self._count(GroundTruthLabelRow)

    def break_count(self) -> int:
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
            select(
                GroundTruthLabelRow.break_type,
                func.count(),
            )
            .group_by(GroundTruthLabelRow.break_type)
            .order_by(GroundTruthLabelRow.break_type)
        ).all()

        return {
            str(break_type) if break_type is not None else "none": int(count)
            for break_type, count in rows
        }


class QuarantineRepository(_Repository):
    """Rows rejected during ingestion validation."""

    def add_many(self, run_id: str, rows: Iterable[Any]) -> int:
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

        self.session.execute(
            insert(QuarantinedRowRow),
            mappings,
        )
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
    """Ingestion run headers."""

    def start(
        self,
        run_id: str,
        *,
        source_dir: str,
        started_at: datetime,
        scenario: str | None = None,
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
        """Finish exactly one ingestion run."""
        result = self.session.execute(
            update(IngestRunRow)
            .where(IngestRunRow.run_id == run_id)
            .values(
                finished_at=finished_at,
                counts=counts,
                status=status,
            )
        )

        if result.rowcount != 1:
            raise KeyError(f"unknown ingest run {run_id!r}")

        self.session.flush()

    def get(self, run_id: str) -> IngestRunRow | None:
        return self.session.get(IngestRunRow, run_id)

    def latest(self) -> IngestRunRow | None:
        return self.session.scalars(
            select(IngestRunRow)
            .order_by(IngestRunRow.started_at.desc())
            .limit(1)
        ).first()

    def count(self) -> int:
        return self._count(IngestRunRow)


class MatchRepository(_Repository):
    """Reconciliation matches."""

    def upsert(self, match: Match) -> None:
        self.session.merge(MatchRow(**MatchRow.values(match)))
        self.session.flush()

    def get(self, match_id: str) -> Match | None:
        row = self.session.get(MatchRow, match_id)
        return row.to_domain() if row else None

    def for_record(
        self,
        record_type: str,
        record_id: str,
    ) -> list[Match]:
        rows = self.session.scalars(select(MatchRow)).all()

        result: list[Match] = []

        for row in rows:
            if any(
                leg.get("record_type") == record_type
                and leg.get("record_id") == record_id
                for leg in row.legs
            ):
                result.append(row.to_domain())

        return result

    def count(self) -> int:
        return self._count(MatchRow)


class BreakRepository(_Repository):
    """Exception queue repository."""

    def upsert(self, brk: Break) -> None:
        self.session.merge(BreakRow(**BreakRow.values(brk)))
        self.session.flush()

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
            statement = statement.where(
                BreakRow.status == status
            )

        if break_type is not None:
            statement = statement.where(
                BreakRow.break_type == break_type
            )

        if min_amount_minor is not None:
            statement = statement.where(
                BreakRow.amount_at_risk_minor >= min_amount_minor
            )

        total = int(
            self.session.scalar(
                select(func.count()).select_from(
                    statement.subquery()
                )
            )
            or 0
        )

        rows = self.session.scalars(
            statement
            .order_by(
                BreakRow.amount_at_risk_minor.desc(),
                BreakRow.break_id,
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return [row.to_domain() for row in rows], total

    def count(self) -> int:
        return self._count(BreakRow)


class JournalRepository(_Repository):
    """Journal entries. Posted entries are immutable; corrections reverse."""

    def propose(self, entry: JournalEntry) -> None:
        self.session.merge(
            JournalEntryRow(**JournalEntryRow.values(entry))
        )
        self.session.flush()

    def get(self, entry_id: str) -> JournalEntry | None:
        row = self.session.get(JournalEntryRow, entry_id)
        return row.to_domain() if row is not None else None

    def all(self) -> list[JournalEntry]:
        rows = self.session.scalars(
            select(JournalEntryRow)
            .order_by(JournalEntryRow.entry_id)
        ).all()
        return [row.to_domain() for row in rows]

    def by_break(self, break_id: str) -> list[JournalEntry]:
        rows = self.session.scalars(
            select(JournalEntryRow)
            .where(JournalEntryRow.break_id == break_id)
        ).all()
        return [row.to_domain() for row in rows]

    def approve(
        self,
        entry_id: str,
        approved_by: str,
    ) -> JournalEntry | None:
        entry = self.get(entry_id)

        if entry is None:
            return None

        approved = entry.model_copy(
            update={
                "status": JournalEntryStatus.APPROVED,
                "approved_by": approved_by,
            }
        )

        self.session.merge(
            JournalEntryRow(**JournalEntryRow.values(approved))
        )
        self.session.flush()

        return approved

    def clearing_account_balance_minor(self) -> int:
        rows = self.session.scalars(
            select(JournalEntryRow)
        ).all()

        net_clearing = 0

        for row in rows:
            for line in row.lines:
                if line.get("account_code") == "1200":
                    net_clearing += (
                        line.get("debit_minor", 0)
                        - line.get("credit_minor", 0)
                    )

        return net_clearing


class ReconRunRepository(_Repository):
    """Reconciliation run headers."""

    def upsert(self, run: ReconRun) -> None:
        row = ReconRunRow(
            run_id=run.run_id,
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=run.status,
            autonomy_level=run.autonomy_level,
            counts=run.counts,
        )
        self.session.merge(row)
        self.session.flush()

    def get(self, run_id: str) -> ReconRun | None:
        row = self.session.get(ReconRunRow, run_id)
        return row.to_domain() if row is not None else None

    def latest(self) -> ReconRun | None:
        row = self.session.scalars(
            select(ReconRunRow)
            .order_by(ReconRunRow.started_at.desc())
        ).first()
        return row.to_domain() if row is not None else None

    def all(self) -> list[ReconRun]:
        rows = self.session.scalars(
            select(ReconRunRow)
            .order_by(ReconRunRow.started_at.desc())
        ).all()
        return [row.to_domain() for row in rows]


class AuditRepository(_Repository):
    """Tamper-evident audit trail repository."""

    def append(self, event: AuditEvent) -> None:
        self.session.merge(
            AuditEventRow(
                event_id=event.event_id,
                sequence_number=self._next_sequence_number(),
                timestamp=event.ts,
                event_type=event.action.value,
                actor=event.actor,
                target_type=(
                    event.subject_ids[0]
                    if event.subject_ids
                    else ""
                ),
                target_id=(
                    event.subject_ids[0]
                    if event.subject_ids
                    else ""
                ),
                payload={
                    "actor_id": event.actor_id,
                    "subject_ids": list(event.subject_ids),
                    "payload": dict(event.payload),
                    "rationale": event.rationale,
                    "confidence": event.confidence,
                    "inputs_hash": event.inputs_hash,
                },
                prev_hash=event.prev_event_hash,
                hash=event.event_hash,
            )
        )
        self.session.flush()

    def _next_sequence_number(self) -> int:
        current = self.session.scalar(
            select(func.max(AuditEventRow.sequence_number))
        )
        return int(current or 0) + 1

    def list(
        self,
        *,
        subject_id: str | None = None,
        actor: DecisionActor | None = None,
        action: AuditAction | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditEventRow], int]:
        statement = select(AuditEventRow)

        if subject_id is not None:
            statement = statement.where(
                AuditEventRow.target_id == subject_id
            )

        if actor is not None:
            statement = statement.where(
                AuditEventRow.actor == actor
            )

        if action is not None:
            statement = statement.where(
                AuditEventRow.event_type == action.value
            )

        total = int(
            self.session.scalar(
                select(func.count()).select_from(
                    statement.subquery()
                )
            )
            or 0
        )

        rows = self.session.scalars(
            statement
            .order_by(AuditEventRow.sequence_number)
            .offset(offset)
            .limit(limit)
        ).all()

        return rows, total

    def latest_hash(self) -> str:
        row = self.session.scalars(
            select(AuditEventRow)
            .order_by(AuditEventRow.sequence_number.desc())
        ).first()

        return row.hash if row is not None else "0" * 64