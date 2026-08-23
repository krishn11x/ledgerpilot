"""Repository layer: the only code that issues queries.

PLACEHOLDER -- signatures only.

Repositories exist so that the reconciliation engine and the agent's tools can
be handed a narrow, typed data-access interface rather than a Session. Two
payoffs: the engine can be tested against in-memory fakes, and the agent's
tool surface can be made provably read-only by construction.
"""

from __future__ import annotations

from typing import Protocol

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


class OrderRepository:
    """TODO(phase-1)."""

    def bulk_upsert(self, orders: list[Order]) -> int:
        raise NotImplementedError


class GatewayRepository:
    """TODO(phase-1)."""

    def bulk_upsert(self, txns: list[GatewayTxn]) -> int:
        raise NotImplementedError

    def unsettled(self) -> list[GatewayTxn]:
        """TODO: captured transactions with no payout_id -- UNSETTLED candidates."""
        raise NotImplementedError


class BankRepository:
    """TODO(phase-1)."""

    def bulk_upsert(self, txns: list[BankTxn]) -> int:
        raise NotImplementedError


class MatchRepository:
    """TODO(phase-2). Writes must be idempotent on the content-hashed match_id."""

    def upsert(self, match: Match) -> None:
        raise NotImplementedError

    def for_record(self, record_type: str, record_id: str) -> list[Match]:
        raise NotImplementedError


class BreakRepository:
    """TODO(phase-2). Backs the exception queue."""

    def upsert(self, brk: Break) -> None:
        raise NotImplementedError

    def query(
        self,
        *,
        status: BreakStatus | None = None,
        break_type: BreakType | None = None,
        min_amount_minor: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Break], int]:
        """TODO: return (page, total_count) for the queue."""
        raise NotImplementedError


class JournalRepository:
    """TODO(phase-4). Entries are immutable once posted; corrections reverse."""

    def propose(self, entry: JournalEntry) -> None:
        raise NotImplementedError

    def clearing_account_balance_minor(self) -> int:
        """TODO: Gateway Clearing balance -- must equal captured-but-unsettled.

        This is the self-proving control: a non-zero divergence *is* an
        unreconciled break, detected by the ledger itself.
        """
        raise NotImplementedError
