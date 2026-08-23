"""Happy-path data generation.

Builds an internally consistent four-ledger chain where everything reconciles
perfectly. Breaks are injected afterwards by ``synth.breaks``, which keeps the
two concerns separable: a bug in break injection cannot silently corrupt the
baseline.

Realism that matters for the demo:
  * T+2 settlement lag, so timing differences arise naturally at period edges
  * batched payouts, so the N:1 aggregate pass has real work to do
  * messy bank narration in several vendor formats, some with no UTR at all
  * a minority of USD orders settled into an INR account, to exercise FX
  * weekday-skewed volume, since a flat distribution looks synthetic

Determinism is a hard requirement, not a nicety: the evaluation harness
attributes a match-rate change to a code change, which is only valid if the
data is byte-identical across runs and machines. Two consequences:

*Only* ``random.Random(seed)`` is used. No ``Faker``, no module-level
``random``, no ``date.today()``. Faker would tie the dataset to a library
version, and "today" would make yesterday's baseline unreproducible -- so the
period is anchored to a fixed constant instead.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from ledgerpilot.config import settings
from ledgerpilot.domain.enums import TxnDirection
from ledgerpilot.domain.models import BankTxn, GatewayTxn, Order, PayoutBatch
from ledgerpilot.domain.money import FxRate, Money
from ledgerpilot.domain.policy import FeeSchedule
from ledgerpilot.ingest.loaders import (
    BANK_COLUMNS,
    COLUMNS,
    FILENAMES,
    GATEWAY_COLUMNS,
    ORDER_COLUMNS,
    PAYOUT_COLUMNS,
)

#: The last day of the reconciliation period. A constant, not ``today``: the
#: baseline dataset has to be reproducible next month as well as this one.
PERIOD_END = date(2026, 7, 31)

#: Booked USD/INR rate. Foreign settlements are compared against this, so an
#: FX break is "the bank converted at a different rate than we booked".
BOOKED_USD_INR = Decimal("83.25")

#: Orders per weekday index (Mon=0). Commerce volume dips at the weekend.
_WEEKDAY_WEIGHTS: tuple[float, ...] = (1.15, 1.10, 1.05, 1.05, 1.20, 0.75, 0.70)

#: INR price points in paise, with their relative frequency. Long right tail.
_INR_BANDS: tuple[tuple[int, float], ...] = (
    (49_900, 0.30),
    (129_900, 0.25),
    (249_900, 0.20),
    (599_900, 0.15),
    (1_499_900, 0.08),
    (4_999_900, 0.02),
)

#: USD price points in cents, for the minority of foreign orders.
_USD_BANDS: tuple[tuple[int, float], ...] = (
    (999, 0.35),
    (2_999, 0.30),
    (9_999, 0.25),
    (24_999, 0.10),
)

#: Hour-of-day weights. Indian e-commerce peaks late evening.
_HOUR_WEIGHTS: tuple[float, ...] = (
    0.3, 0.2, 0.1, 0.1, 0.2, 0.4, 0.7, 1.0, 1.3, 1.5, 1.6, 1.5,
    1.4, 1.3, 1.3, 1.4, 1.6, 1.9, 2.3, 2.6, 2.4, 1.8, 1.1, 0.6,
)  # fmt: skip

_PROVIDERS: tuple[str, ...] = ("RAZORPAY", "PAYU", "CASHFREE", "BILLDESK", "CCAVENUE")

_MERCHANT_SUFFIXES: tuple[str, ...] = (
    "SOFTWARE PVT LTD",
    "TECHNOLOGIES PVT LTD",
    "PAYMENTS INDIA",
    "SERVICES LLP",
)


@dataclass(slots=True)
class GeneratedDataset:
    """A complete, internally consistent set of source records."""

    orders: list[Order]
    gateway_txns: list[GatewayTxn]
    payouts: list[PayoutBatch]
    bank_txns: list[BankTxn]
    seed: int
    period_start: date
    period_end: date


def narration_templates() -> list[str]:
    """The several formats banks emit, to exercise reference extraction.

    Three of these deliberately omit the UTR: those are the records that force
    the subset-sum fallback and the agent's narration parser. Reference
    extraction that only ever sees well-formed input proves nothing.
    """
    return [
        "NEFT-{provider} {suffix}-UTR{utr}-STLMNT/{month}",
        "IMPS/{utr}/{provider}/SETTLEMENT",
        "RTGS CR {provider} UTR: {utr} PAYOUT {payout}",
        "ACH CREDIT {provider} SETTLMNT REF {utr}",
        "{provider} PAYOUT {payout} UTR{utr}",
        "NEFT CR-{provider}-SETTLEMENT-{month}",  # no UTR
        "FUND TRANSFER FRM {provider} {suffix}",  # no UTR, no payout ref
        "MERCHANT SETTLEMENT {month} BATCH CREDIT",  # nothing at all
    ]


class SyntheticGenerator:
    """Seeded generator for a perfectly reconciling four-ledger chain.

    Every stage is a pure function of the seed. ``_batch_into_payouts``
    is the one exception to "no mutation": it rewrites the ``payout_id`` of the
    transactions it batches, in place in the caller's list, because a frozen
    record cannot learn its own batch until the batch exists.
    """

    def __init__(
        self,
        *,
        seed: int,
        period_days: int,
        fee: FeeSchedule | None = None,
        period_end: date | None = None,
        fx_share: float = 0.08,
    ) -> None:
        self.seed = seed
        self.period_days = period_days
        self.rng = random.Random(seed)
        self.fee = fee or FeeSchedule(
            bps=settings.gateway_fee_bps,
            flat_minor=settings.gateway_fee_flat_minor,
            tax_bps=settings.gateway_tax_bps,
        )
        self.period_end = period_end or PERIOD_END
        self.period_start = self.period_end - timedelta(days=period_days - 1)
        self.base_currency = settings.base_currency
        self.settlement_lag_days = settings.settlement_lag_days
        self.fx_share = fx_share
        self._fx = FxRate(
            base="USD",
            quote=self.base_currency,
            rate=BOOKED_USD_INR,
            as_of=self.period_end.isoformat(),
        )

    # -- Public -------------------------------------------------------------

    def generate(self, *, order_count: int) -> GeneratedDataset:
        """Produce a perfectly reconciling dataset.

        "Perfectly" is checkable and is checked: for every payout, the sum of
        its transactions' net equals ``expected_net_minor`` equals the bank
        credit (converted at the booked rate). ``test_synth`` asserts it.
        """
        if order_count < 1:
            raise ValueError(f"order_count must be positive, got {order_count}")

        orders = self._make_orders(order_count)
        gateway_txns = self._capture_payments(orders)
        payouts = self._batch_into_payouts(gateway_txns)
        bank_txns = self._credit_bank(payouts)

        return GeneratedDataset(
            orders=orders,
            gateway_txns=gateway_txns,
            payouts=payouts,
            bank_txns=bank_txns,
            seed=self.seed,
            period_start=self.period_start,
            period_end=self.period_end,
        )

    # -- Stages -------------------------------------------------------------

    def _make_orders(self, count: int) -> list[Order]:
        """Weekday- and hour-skewed orders, a minority of them in USD."""
        days = [self.period_start + timedelta(days=i) for i in range(self.period_days)]
        day_weights = [_WEEKDAY_WEIGHTS[day.weekday()] for day in days]
        hours = list(range(24))

        orders: list[Order] = []
        for index in range(1, count + 1):
            day = self.rng.choices(days, weights=day_weights, k=1)[0]
            hour = self.rng.choices(hours, weights=list(_HOUR_WEIGHTS), k=1)[0]
            placed_at = datetime.combine(
                day,
                time(hour, self.rng.randrange(60), self.rng.randrange(60)),
                tzinfo=UTC,
            )
            currency = "USD" if self.rng.random() < self.fx_share else self.base_currency
            orders.append(
                Order(
                    order_id=f"ORD-{index:07d}",
                    customer_id=f"CUST-{self.rng.randrange(1, max(2, count // 3)):06d}",
                    gross_minor=self._price(currency),
                    currency=currency,
                    placed_at=placed_at,
                    status="paid",
                )
            )
        orders.sort(key=lambda order: (order.placed_at, order.order_id))
        return orders

    def _price(self, currency: str) -> int:
        """A price point plus deterministic whole-major-unit jitter."""
        bands = _USD_BANDS if currency == "USD" else _INR_BANDS
        base = self.rng.choices(
            [amount for amount, _ in bands], weights=[weight for _, weight in bands], k=1
        )[0]
        scale = 100  # both INR and USD have two decimal places
        jitter_units = self.rng.randint(-base // (scale * 10), base // (scale * 10))
        return max(scale, base + jitter_units * scale)

    def _capture_payments(self, orders: list[Order]) -> list[GatewayTxn]:
        """Apply the fee schedule to derive fee/tax/net per transaction.

        Capture happens minutes after the order in the happy path, which is why
        a capture that lands days later is worth flagging.
        """
        txns: list[GatewayTxn] = []
        for index, order in enumerate(orders, start=1):
            breakdown = self.fee.breakdown(order.gross_minor)
            captured_at = order.placed_at + timedelta(seconds=self.rng.randrange(20, 900))
            txns.append(
                GatewayTxn(
                    txn_id=f"PAY-{index:07d}",
                    order_ref=order.order_id,
                    gross_minor=breakdown.gross_minor,
                    fee_minor=breakdown.fee_minor,
                    tax_minor=breakdown.tax_minor,
                    net_minor=breakdown.net_minor,
                    currency=order.currency,
                    status="captured",
                    payout_id=None,  # assigned by _batch_into_payouts
                    captured_at=captured_at,
                )
            )
        return txns

    def _batch_into_payouts(self, txns: list[GatewayTxn]) -> list[PayoutBatch]:
        """Group by settlement date (T+2) and currency, sum net, assign a UTR.

        Batches are single-currency because gateways settle each currency into
        its own account. Mixed batches would make the aggregate pass
        unsolvable rather than merely hard.

        Mutates ``txns`` in place to stamp each transaction with its
        ``payout_id`` -- the one place in this module that rewrites a record.
        """
        groups: dict[tuple[date, str], list[int]] = {}
        for position, txn in enumerate(txns):
            settled_on = txn.captured_at.date() + timedelta(days=self.settlement_lag_days)
            groups.setdefault((settled_on, txn.currency), []).append(position)

        payouts: list[PayoutBatch] = []
        for index, key in enumerate(sorted(groups), start=1):
            settled_on, currency = key
            positions = groups[key]
            payout_id = f"POUT-{index:05d}"
            total_net = 0
            for position in positions:
                txn = txns[position]
                txns[position] = txn.model_copy(update={"payout_id": payout_id})
                total_net += txn.net_minor
            payouts.append(
                PayoutBatch(
                    payout_id=payout_id,
                    expected_net_minor=total_net,
                    txn_count=len(positions),
                    currency=currency,
                    settled_on=settled_on,
                    utr=f"{self.rng.randrange(10**11, 10**12)}",
                )
            )
        return payouts

    def _credit_bank(self, payouts: list[PayoutBatch]) -> list[BankTxn]:
        """One credit per payout, with narration in a random vendor format.

        The bank account is single-currency, so a USD payout arrives as an INR
        credit converted at the booked rate. That conversion is what makes
        FX_VARIANCE detectable rather than merely assumed.
        """
        templates = narration_templates()
        lines: list[BankTxn] = []
        for index, payout in enumerate(payouts, start=1):
            amount = self.credited_amount(payout)
            lines.append(
                BankTxn(
                    bank_txn_id=f"BNK-{index:07d}",
                    value_date=payout.settled_on,
                    amount_minor=amount.minor,
                    direction=TxnDirection.CREDIT,
                    currency=amount.currency,
                    narration=self._narration(payout, self.rng.choice(templates)),
                    utr=None,  # the bank's structured column is empty; parse it out
                )
            )
        return lines

    # -- Helpers ------------------------------------------------------------

    def credited_amount(self, payout: PayoutBatch) -> Money:
        """What the bank should credit for ``payout``, in the account currency."""
        net = Money(payout.expected_net_minor, payout.currency)
        if payout.currency == self.base_currency:
            return net
        return self._fx.convert(net)

    def _narration(self, payout: PayoutBatch, template: str) -> str:
        """Render one narration. Deliberately not normalised."""
        return template.format(
            provider=self.rng.choice(_PROVIDERS),
            suffix=self.rng.choice(_MERCHANT_SUFFIXES),
            utr=payout.utr or "",
            payout=payout.payout_id,
            month=payout.settled_on.strftime("%b").upper(),
        )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _order_row(order: Order) -> dict[str, str]:
    return {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "gross_minor": str(order.gross_minor),
        "currency": order.currency,
        "placed_at": order.placed_at.isoformat(),
        "status": order.status,
    }


def _gateway_row(txn: GatewayTxn) -> dict[str, str]:
    return {
        "txn_id": txn.txn_id,
        "order_ref": txn.order_ref or "",
        "gross_minor": str(txn.gross_minor),
        "fee_minor": str(txn.fee_minor),
        "tax_minor": str(txn.tax_minor),
        "net_minor": str(txn.net_minor),
        "currency": txn.currency,
        "status": txn.status,
        "payout_id": txn.payout_id or "",
        "captured_at": txn.captured_at.isoformat(),
    }


def _payout_row(payout: PayoutBatch) -> dict[str, str]:
    return {
        "payout_id": payout.payout_id,
        "expected_net_minor": str(payout.expected_net_minor),
        "txn_count": str(payout.txn_count),
        "currency": payout.currency,
        "settled_on": payout.settled_on.isoformat(),
        "utr": payout.utr or "",
    }


def _bank_row(txn: BankTxn) -> dict[str, str]:
    return {
        "bank_txn_id": txn.bank_txn_id,
        "value_date": txn.value_date.isoformat(),
        # Formatted major units: what a bank statement export actually contains.
        "amount": Money(txn.amount_minor, txn.currency).format(symbol=False),
        "direction": txn.direction.value,
        "currency": txn.currency,
        "narration": txn.narration,
        "utr": txn.utr or "",
    }


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_dataset(dataset: GeneratedDataset, out_dir: Path) -> dict[str, Path]:
    """Write CSVs plus a manifest recording seed and parameters.

    The manifest is not decoration. Without the seed and the fee schedule
    recorded next to the data, a metrics table six commits later cannot be
    tied to the dataset that produced it.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    for source, rows in (
        ("orders", [_order_row(record) for record in dataset.orders]),
        ("gateway_txns", [_gateway_row(record) for record in dataset.gateway_txns]),
        ("payouts", [_payout_row(record) for record in dataset.payouts]),
        ("bank_txns", [_bank_row(record) for record in dataset.bank_txns]),
    ):
        path = out_dir / FILENAMES[source]
        _write_csv(path, COLUMNS[source], rows)
        written[source] = path

    manifest = out_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "seed": dataset.seed,
                "period_start": dataset.period_start.isoformat(),
                "period_end": dataset.period_end.isoformat(),
                "counts": {
                    "orders": len(dataset.orders),
                    "gateway_txns": len(dataset.gateway_txns),
                    "payouts": len(dataset.payouts),
                    "bank_txns": len(dataset.bank_txns),
                },
                "fee_schedule": {
                    "bps": settings.gateway_fee_bps,
                    "flat_minor": settings.gateway_fee_flat_minor,
                    "tax_bps": settings.gateway_tax_bps,
                    "rule": "fee = round(gross * bps) + flat; tax = round(fee * tax_bps); "
                    "net = gross - fee - tax",
                },
                "booked_usd_inr": str(BOOKED_USD_INR),
                "settlement_lag_days": settings.settlement_lag_days,
                "columns": {
                    "orders": list(ORDER_COLUMNS),
                    "gateway_txns": list(GATEWAY_COLUMNS),
                    "payouts": list(PAYOUT_COLUMNS),
                    "bank_txns": list(BANK_COLUMNS),
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    written["manifest"] = manifest
    return written
