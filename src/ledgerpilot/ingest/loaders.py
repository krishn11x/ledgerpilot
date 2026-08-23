"""Read source files into typed domain records.

Each loader is deliberately dumb: parse, coerce types, return records. No
matching, no normalisation beyond type coercion, no validation. Real
gateway/bank exports get plugged in here later by adding a loader; nothing
downstream changes.

This module also owns the **canonical column names** for every CSV the project
reads or writes. ``synth.generator`` imports these constants rather than
repeating the header strings, so a writer/reader mismatch is a type error at
import time instead of a KeyError halfway through a demo. ``test_ingest``
asserts the two sides agree.

One deliberate asymmetry in the schemas: the three internal files carry
integer **minor units** in columns named ``*_minor``, while the bank statement
carries a formatted major-unit ``amount`` column, because that is what banks
actually emit. A column named ``gross_minor`` holding ``1200.00`` is
underdetermined input, so the minor-unit parser refuses it rather than picking
a reading; the bank column goes through
:func:`ledgerpilot.ingest.normalize.normalize_currency_amount`.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ledgerpilot.domain.enums import TxnDirection
from ledgerpilot.domain.models import BankTxn, GatewayTxn, Order, PayoutBatch
from ledgerpilot.ingest.normalize import normalize_currency_amount, parse_flexible_date

# ---------------------------------------------------------------------------
# Canonical CSV schemas -- one definition, shared by the writer and the reader
# ---------------------------------------------------------------------------

ORDER_COLUMNS: tuple[str, ...] = (
    "order_id",
    "customer_id",
    "gross_minor",
    "currency",
    "placed_at",
    "status",
)

GATEWAY_COLUMNS: tuple[str, ...] = (
    "txn_id",
    "order_ref",
    "gross_minor",
    "fee_minor",
    "tax_minor",
    "net_minor",
    "currency",
    "status",
    "payout_id",
    "captured_at",
)

PAYOUT_COLUMNS: tuple[str, ...] = (
    "payout_id",
    "expected_net_minor",
    "txn_count",
    "currency",
    "settled_on",
    "utr",
)

BANK_COLUMNS: tuple[str, ...] = (
    "bank_txn_id",
    "value_date",
    "amount",
    "direction",
    "currency",
    "narration",
    "utr",
)

#: File name per source, so callers never hard-code a stem.
FILENAMES: dict[str, str] = {
    "orders": "orders.csv",
    "gateway_txns": "gateway_txns.csv",
    "payouts": "payouts.csv",
    "bank_txns": "bank_txns.csv",
}

#: Expected header per source, keyed the same way.
COLUMNS: dict[str, tuple[str, ...]] = {
    "orders": ORDER_COLUMNS,
    "gateway_txns": GATEWAY_COLUMNS,
    "payouts": PAYOUT_COLUMNS,
    "bank_txns": BANK_COLUMNS,
}


# ---------------------------------------------------------------------------
# Raw reading
# ---------------------------------------------------------------------------


def read_rows(path: Path, *, expected: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Read a CSV into a list of string-valued dicts.

    Kept separate from the typed loaders because validation happens on raw rows:
    a row that cannot be coerced still has to reach quarantine with its original
    contents intact, which is impossible once coercion has thrown.

    A missing or reordered header is a file-level error rather than a per-row
    one -- every row would fail, and reporting that ten thousand times is
    noise rather than information.
    """
    if not path.exists():
        raise FileNotFoundError(f"no such input file: {path}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        if expected is not None and set(header) != set(expected):
            missing = sorted(set(expected) - set(header))
            extra = sorted(set(header) - set(expected))
            raise ValueError(
                f"{path.name}: header mismatch (missing={missing}, unexpected={extra})"
            )
        return [dict(row) for row in reader]


# ---------------------------------------------------------------------------
# Scalar coercion
# ---------------------------------------------------------------------------


def _required(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value is None or str(value).strip() == "":
        raise ValueError(f"missing required field {key!r}")
    return str(value).strip()


def _optional(row: dict[str, Any], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_minor(raw: str, field: str) -> int:
    """Parse an integer minor-unit column. Digits and an optional sign, nothing else.

    Refuses ``"1200.00"``: in a column named ``*_minor`` that is either twelve
    rupees written wrongly or twelve hundred rupees written wrongly, and there
    is no way to tell which.
    """
    text = raw.strip()
    body = text[1:] if text[:1] in "+-" else text
    if not body.isdigit():
        raise ValueError(f"{field}: {raw!r} is not an integer number of minor units")
    return int(text)


def parse_int(raw: str, field: str) -> int:
    text = raw.strip()
    body = text[1:] if text[:1] in "+-" else text
    if not body.isdigit():
        raise ValueError(f"{field}: {raw!r} is not an integer")
    return int(text)


def parse_timestamp(raw: str, field: str) -> datetime:
    """Parse an ISO-8601 timestamp. Written by us, so no flexibility is owed."""
    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError:
        raise ValueError(f"{field}: {raw!r} is not an ISO-8601 timestamp") from None


def parse_date(raw: str, field: str) -> date:
    """Parse a date column through the flexible, ambiguity-refusing parser."""
    try:
        return parse_flexible_date(raw)
    except ValueError as exc:
        raise ValueError(f"{field}: {exc}") from None


# ---------------------------------------------------------------------------
# Row -> record
# ---------------------------------------------------------------------------


def to_order(row: dict[str, Any]) -> Order:
    """Coerce one raw row into an :class:`Order`. Raises ``ValueError`` if it cannot."""
    return Order(
        order_id=_required(row, "order_id"),
        customer_id=_required(row, "customer_id"),
        gross_minor=parse_minor(_required(row, "gross_minor"), "gross_minor"),
        currency=_required(row, "currency"),
        placed_at=parse_timestamp(_required(row, "placed_at"), "placed_at"),
        status=_required(row, "status"),
    )


def to_gateway_txn(row: dict[str, Any]) -> GatewayTxn:
    """Coerce one raw row into a :class:`GatewayTxn`."""
    return GatewayTxn(
        txn_id=_required(row, "txn_id"),
        order_ref=_optional(row, "order_ref"),
        gross_minor=parse_minor(_required(row, "gross_minor"), "gross_minor"),
        fee_minor=parse_minor(_required(row, "fee_minor"), "fee_minor"),
        tax_minor=parse_minor(_required(row, "tax_minor"), "tax_minor"),
        net_minor=parse_minor(_required(row, "net_minor"), "net_minor"),
        currency=_required(row, "currency"),
        status=_required(row, "status"),
        payout_id=_optional(row, "payout_id"),
        captured_at=parse_timestamp(_required(row, "captured_at"), "captured_at"),
    )


def to_payout(row: dict[str, Any]) -> PayoutBatch:
    """Coerce one raw row into a :class:`PayoutBatch`."""
    return PayoutBatch(
        payout_id=_required(row, "payout_id"),
        expected_net_minor=parse_minor(_required(row, "expected_net_minor"), "expected_net_minor"),
        txn_count=parse_int(_required(row, "txn_count"), "txn_count"),
        currency=_required(row, "currency"),
        settled_on=parse_date(_required(row, "settled_on"), "settled_on"),
        utr=_optional(row, "utr"),
    )


def to_bank_txn(row: dict[str, Any]) -> BankTxn:
    """Coerce one raw row into a :class:`BankTxn`, narration untouched.

    ``narration`` is taken verbatim -- not stripped, not uppercased. It is
    evidence, and it has to appear in the audit trail exactly as the bank sent
    it. Normalisation happens downstream, on copies.
    """
    currency = _required(row, "currency")
    direction_raw = _required(row, "direction").lower()
    try:
        direction = TxnDirection(direction_raw)
    except ValueError:
        allowed = ", ".join(d.value for d in TxnDirection)
        raise ValueError(f"direction: {direction_raw!r} not one of {allowed}") from None

    narration = row.get("narration")
    if narration is None:
        raise ValueError("missing required field 'narration'")

    return BankTxn(
        bank_txn_id=_required(row, "bank_txn_id"),
        value_date=parse_date(_required(row, "value_date"), "value_date"),
        amount_minor=normalize_currency_amount(_required(row, "amount"), currency),
        direction=direction,
        currency=currency,
        narration=str(narration),
        utr=_optional(row, "utr"),
    )


# ---------------------------------------------------------------------------
# Whole-file loaders
# ---------------------------------------------------------------------------


def load_orders(path: Path) -> list[Order]:
    """Read orders CSV -> Order records, amounts as integer minor units."""
    return [to_order(row) for row in read_rows(path, expected=ORDER_COLUMNS)]


def load_gateway_txns(path: Path) -> list[GatewayTxn]:
    """Read gateway export CSV -> GatewayTxn records."""
    return [to_gateway_txn(row) for row in read_rows(path, expected=GATEWAY_COLUMNS)]


def load_payouts(path: Path) -> list[PayoutBatch]:
    """Read settlement report CSV -> PayoutBatch records."""
    return [to_payout(row) for row in read_rows(path, expected=PAYOUT_COLUMNS)]


def load_bank_txns(path: Path) -> list[BankTxn]:
    """Read bank statement CSV -> BankTxn records, preserving raw narration.

    Narration is stored verbatim as well as normalised -- the raw string is
    evidence and has to appear untouched in the audit trail.
    """
    return [to_bank_txn(row) for row in read_rows(path, expected=BANK_COLUMNS)]
