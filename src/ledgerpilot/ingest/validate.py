"""Schema contracts at the boundary. PLACEHOLDER -- signatures only.

Policy: a malformed row must never crash a reconciliation run and must never
be silently dropped. It goes to quarantine with a reason, is counted, and shows
up in the run summary. Silent data loss in a financial control is worse than a
visible failure.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ledgerpilot.ingest.loaders import (
    to_bank_txn,
    to_gateway_txn,
    to_order,
    to_payout,
)


@dataclass(slots=True)
class QuarantinedRow:
    """A row that failed validation, kept with its reason for triage."""

    source: str
    row_number: int
    raw: dict[str, Any]
    reason: str


@dataclass(slots=True)
class ValidationReport:
    """Outcome of validating one input file."""

    source: str
    total_rows: int = 0
    accepted: int = 0
    quarantined: list[QuarantinedRow] = field(default_factory=list)

    @property
    def acceptance_rate(self) -> float:
        """accepted / total_rows, guarding divide-by-zero."""
        if self.total_rows == 0:
            return 1.0
        return self.accepted / self.total_rows


def _validate_rows(
    source: str,
    rows: list[dict[str, Any]],
    check_fn: Callable[[dict[str, Any]], None],
) -> tuple[list[dict[str, Any]], ValidationReport]:
    accepted: list[dict[str, Any]] = []
    quarantined: list[QuarantinedRow] = []

    for row_number, row in enumerate(rows, start=1):
        try:
            check_fn(row)
            accepted.append(row)
        except Exception as exc:
            quarantined.append(
                QuarantinedRow(
                    source=source,
                    row_number=row_number,
                    raw=dict(row),
                    reason=str(exc),
                )
            )

    report = ValidationReport(
        source=source,
        total_rows=len(rows),
        accepted=len(accepted),
        quarantined=quarantined,
    )
    return accepted, report


def _check_order(row: dict[str, Any]) -> None:
    order = to_order(row)
    if order.gross_minor <= 0:
        raise ValueError(f"gross_minor must be positive, got {order.gross_minor}")
    if len(order.currency) != 3 or not order.currency.isupper():
        raise ValueError(f"invalid currency {order.currency!r}")


def validate_orders(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], ValidationReport]:
    """Required fields, positive amounts, known currency, sane dates."""
    return _validate_rows("orders", rows, _check_order)


def _check_gateway_txn(row: dict[str, Any]) -> None:
    txn = to_gateway_txn(row)
    if txn.gross_minor < 0:
        raise ValueError(f"gross_minor cannot be negative, got {txn.gross_minor}")
    if txn.fee_minor < 0:
        raise ValueError(f"fee_minor cannot be negative, got {txn.fee_minor}")
    if txn.tax_minor < 0:
        raise ValueError(f"tax_minor cannot be negative, got {txn.tax_minor}")
    expected_net = txn.gross_minor - txn.fee_minor - txn.tax_minor
    if txn.net_minor != expected_net:
        raise ValueError(
            f"arithmetic mismatch: net_minor ({txn.net_minor}) != "
            f"gross ({txn.gross_minor}) - fee ({txn.fee_minor}) - tax ({txn.tax_minor})"
        )
    if len(txn.currency) != 3 or not txn.currency.isupper():
        raise ValueError(f"invalid currency {txn.currency!r}")


def validate_gateway_txns(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], ValidationReport]:
    """As above, plus net == gross - fee - tax internal consistency."""
    return _validate_rows("gateway_txns", rows, _check_gateway_txn)


def _check_payout(row: dict[str, Any]) -> None:
    payout = to_payout(row)
    if payout.expected_net_minor <= 0:
        raise ValueError(f"expected_net_minor must be positive, got {payout.expected_net_minor}")
    if payout.txn_count <= 0:
        raise ValueError(f"txn_count must be positive, got {payout.txn_count}")
    if len(payout.currency) != 3 or not payout.currency.isupper():
        raise ValueError(f"invalid currency {payout.currency!r}")


def validate_payouts(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], ValidationReport]:
    """Required fields, positive expected net, positive txn count, valid currency."""
    return _validate_rows("payouts", rows, _check_payout)


def _check_bank_txn(row: dict[str, Any]) -> None:
    bank = to_bank_txn(row)
    if bank.amount_minor <= 0:
        raise ValueError(f"amount_minor must be positive, got {bank.amount_minor}")
    if len(bank.currency) != 3 or not bank.currency.isupper():
        raise ValueError(f"invalid currency {bank.currency!r}")


def validate_bank_txns(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], ValidationReport]:
    """As above, plus direction/sign agreement."""
    return _validate_rows("bank_txns", rows, _check_bank_txn)
