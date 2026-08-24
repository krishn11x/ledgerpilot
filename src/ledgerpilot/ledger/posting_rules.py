"""Break type -> proposed journal entry.

Posting rules are deterministic and pure: the same break always produces the
same journal proposal. Every proposed entry is validated for balance before
being returned.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from ledgerpilot.config import settings
from ledgerpilot.domain.enums import BreakType
from ledgerpilot.domain.models import Break, JournalEntry, JournalLine
from ledgerpilot.domain.policy import FeeSchedule
from ledgerpilot.ledger.accounts import (
    BANK,
    CHARGEBACK_EXPENSE,
    FEE_TAX,
    FX_GAIN_LOSS,
    GATEWAY_CLEARING,
    PROCESSING_FEES,
    REFUNDS_PAYABLE,
    SUSPENSE,
    WRITE_OFF,
)
from ledgerpilot.ledger.balance import assert_balanced

# Break types for which no accounting entry should be generated.
NO_ENTRY_BREAK_TYPES: frozenset[BreakType] = frozenset(
    {
        BreakType.TIMING_DIFFERENCE,
        BreakType.UNSETTLED,
    }
)


def _entry_id(brk: Break) -> str:
    """Build a stable journal-entry identifier."""
    return f"JRN-{brk.break_id}"


def _date(brk: Break) -> date:
    """Use the break detection date when available."""
    if brk.detected_at.tzinfo is not None:
        return brk.detected_at.date()
    return datetime.now(UTC).date()


def propose_entry(brk: Break) -> JournalEntry | None:
    """Create the deterministic journal proposal for a break.

    Returns ``None`` when the break is informational or already represented
    in Gateway Clearing.
    """
    if brk.break_type in NO_ENTRY_BREAK_TYPES:
        return None

    if brk.break_type == BreakType.FEE_VARIANCE:
        lines = lines_for_fee_variance(brk)
    elif brk.break_type == BreakType.UNIDENTIFIED_CREDIT:
        lines = lines_for_unidentified_credit(brk)
    elif brk.break_type == BreakType.SHORT_PAYMENT:
        lines = lines_for_short_payment(brk)
    elif brk.break_type == BreakType.OVERPAYMENT:
        lines = lines_for_overpayment(brk)
    elif brk.break_type == BreakType.CHARGEBACK:
        lines = lines_for_chargeback(brk)
    elif brk.break_type == BreakType.FX_VARIANCE:
        lines = lines_for_fx_variance(brk)
    else:
        return None

    entry = JournalEntry(
        entry_id=_entry_id(brk),
        break_id=brk.break_id,
        lines=lines,
        status="proposed",
        posting_date=_date(brk),
        rationale=(
            brk.summary
            or f"{brk.break_type.value.replace('_', ' ').title()} posting"
        ),
        proposed_by="ledgerpilot",
    )

    # No journal is allowed out of this module unless it balances.
    assert_balanced(entry)
    return entry


def lines_for_fee_variance(brk: Break) -> list[JournalLine]:
    """Recognise an unrecorded processing fee and its tax."""
    gross_minor = (
        brk.legs[0].amount_minor
        if brk.legs
        else brk.amount_at_risk_minor
    )

    schedule = FeeSchedule(
        bps=settings.gateway_fee_bps,
        flat_minor=settings.gateway_fee_flat_minor,
        tax_bps=settings.gateway_tax_bps,
    )

    fee_minor = schedule.expected_fee_minor(gross_minor)
    tax_minor = schedule.expected_tax_minor(fee_minor)
    total_minor = fee_minor + tax_minor

    return [
        JournalLine(
            account_code=PROCESSING_FEES,
            debit_minor=fee_minor,
            currency=brk.currency,
        ),
        JournalLine(
            account_code=FEE_TAX,
            debit_minor=tax_minor,
            currency=brk.currency,
        ),
        JournalLine(
            account_code=GATEWAY_CLEARING,
            credit_minor=total_minor,
            currency=brk.currency,
        ),
    ]


def lines_for_unidentified_credit(brk: Break) -> list[JournalLine]:
    """Park an unidentified receipt in suspense."""
    amount = brk.amount_at_risk_minor

    return [
        JournalLine(
            account_code=BANK,
            debit_minor=amount,
            currency=brk.currency,
        ),
        JournalLine(
            account_code=SUSPENSE,
            credit_minor=amount,
            currency=brk.currency,
        ),
    ]


def _received_amount(brk: Break) -> int:
    """Return the observed cash amount represented by the break."""
    if not brk.legs:
        return 0

    return max(line.amount_minor for line in brk.legs)


def lines_for_short_payment(brk: Break) -> list[JournalLine]:
    """Recognise cash received and write off the shortfall."""
    shortfall = brk.amount_at_risk_minor
    received = _received_amount(brk)
    expected = received + shortfall

    return [
        JournalLine(
            account_code=BANK,
            debit_minor=received,
            currency=brk.currency,
        ),
        JournalLine(
            account_code=WRITE_OFF,
            debit_minor=shortfall,
            currency=brk.currency,
        ),
        JournalLine(
            account_code=GATEWAY_CLEARING,
            credit_minor=expected,
            currency=brk.currency,
        ),
    ]


def lines_for_overpayment(brk: Break) -> list[JournalLine]:
    """Recognise excess cash and the resulting refund obligation.

    The excess amount is credited to Refunds Payable rather than being treated
    as revenue or a write-off.
    """
    excess = abs(brk.amount_at_risk_minor)
    received = _received_amount(brk)

    if received == 0:
        received = excess

    expected = received - excess

    if expected < 0:
        expected = 0

    return [
        JournalLine(
            account_code=BANK,
            debit_minor=received,
            currency=brk.currency,
        ),
        JournalLine(
            account_code=GATEWAY_CLEARING,
            credit_minor=expected,
            currency=brk.currency,
        ),
        JournalLine(
            account_code=REFUNDS_PAYABLE,
            credit_minor=excess,
            currency=brk.currency,
        ),
    ]


def lines_for_chargeback(brk: Break) -> list[JournalLine]:
    """Recognise the chargeback expense and cash reversal."""
    amount = brk.amount_at_risk_minor

    return [
        JournalLine(
            account_code=CHARGEBACK_EXPENSE,
            debit_minor=amount,
            currency=brk.currency,
        ),
        JournalLine(
            account_code=BANK,
            credit_minor=amount,
            currency=brk.currency,
        ),
    ]


def lines_for_fx_variance(brk: Break) -> list[JournalLine]:
    """Recognise an FX loss or gain based on the signed variance."""
    amount = brk.amount_at_risk_minor

    if amount >= 0:
        return [
            JournalLine(
                account_code=FX_GAIN_LOSS,
                debit_minor=amount,
                currency=brk.currency,
            ),
            JournalLine(
                account_code=GATEWAY_CLEARING,
                credit_minor=amount,
                currency=brk.currency,
            ),
        ]

    amount = abs(amount)

    return [
        JournalLine(
            account_code=GATEWAY_CLEARING,
            debit_minor=amount,
            currency=brk.currency,
        ),
        JournalLine(
            account_code=FX_GAIN_LOSS,
            credit_minor=amount,
            currency=brk.currency,
        ),
    ]