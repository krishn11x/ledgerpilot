"""Break type -> proposed journal entry. PLACEHOLDER -- signatures only.

The mapping table this module implements:

    FEE_VARIANCE          Dr Processing Fees          Cr Gateway Clearing
                          Dr Processing Fee Tax
    UNIDENTIFIED_CREDIT   Dr Bank                     Cr Suspense
    SHORT_PAYMENT         Dr Bank + Dr Write-off      Cr Gateway Clearing
    OVERPAYMENT           Dr Bank                     Cr Gateway Clearing + Cr Refunds Payable
    FX_VARIANCE           Dr/Cr FX Gain-Loss          Cr/Dr Gateway Clearing
    CHARGEBACK            Dr Chargeback Exp + Dr Rev  Cr Bank
    UNSETTLED             (no entry -- already in Gateway Clearing, in transit)
    TIMING_DIFFERENCE     (no entry -- disclosure only)

FEE_VARIANCE carries two debit legs because the fee schedule levies GST on the
fee itself: an under-reported fee is also an under-reported tax, and account
``5110`` exists precisely so the reclaimable half is not buried in expense.

Note the two break types that correctly produce *no* entry. Posting for an
in-transit item would double-count it; recognising that is part of getting the
accounting right rather than merely generating plausible-looking entries.

Rules are pure functions so they can be unit-tested against expected debits and
credits with no database involved.
"""

from __future__ import annotations

from ledgerpilot.domain.enums import BreakType
from ledgerpilot.domain.models import Break, JournalEntry, JournalLine


def propose_entry(brk: Break) -> JournalEntry | None:
    """TODO: dispatch on break type. Returns None where no entry is warranted.

    Must run every candidate entry through ``ledger.balance.assert_balanced``
    before returning it.
    """
    raise NotImplementedError


def lines_for_fee_variance(brk: Break) -> list[JournalLine]:
    """TODO: recognise the unrecorded processing fee."""
    raise NotImplementedError


def lines_for_unidentified_credit(brk: Break) -> list[JournalLine]:
    """TODO: park the receipt in suspense pending identification."""
    raise NotImplementedError


def lines_for_short_payment(brk: Break) -> list[JournalLine]:
    """TODO: split between cash received and the write-off."""
    raise NotImplementedError


def lines_for_chargeback(brk: Break) -> list[JournalLine]:
    """TODO: reverse revenue and recognise the chargeback cost."""
    raise NotImplementedError


def lines_for_fx_variance(brk: Break) -> list[JournalLine]:
    """TODO: FX gain or loss depending on the sign of the delta."""
    raise NotImplementedError


# Break types that intentionally produce no journal entry.
NO_ENTRY_BREAK_TYPES: frozenset[BreakType] = frozenset(
    {
        BreakType.TIMING_DIFFERENCE,  # disclosure only; not an economic event
        BreakType.UNSETTLED,  # already sitting in Gateway Clearing
    }
)
