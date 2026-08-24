"""Accounting invariants. PLACEHOLDER -- signatures only.

These checks are the reason an LLM is allowed anywhere near a journal entry.
The agent may *draft* an entry; only passing these deterministic assertions
lets it exist. An unbalanced entry is an error, never a warning.
"""

from __future__ import annotations

from ledgerpilot.domain.models import JournalEntry, JournalLine


class UnbalancedEntryError(ValueError):
    """Raised when debits do not equal credits. Never caught and ignored."""


def assert_balanced(entry: JournalEntry) -> None:
    """TODO: raise UnbalancedEntryError unless sum(debits) == sum(credits).

    Compared in integer minor units, so this is an exact equality check with
    no epsilon -- which is only possible because money is never a float.
    """
    debit = sum(line.debit_minor for line in entry.lines)
    credit = sum(line.credit_minor for line in entry.lines)
    if debit != credit:
        raise UnbalancedEntryError(
            f"entry {entry.entry_id} is unbalanced: debits={debit} credits={credit}"
        )
    for line in entry.lines:
        assert_single_sided(line)
    assert_single_currency(entry)


def assert_single_sided(line: JournalLine) -> None:
    """TODO: exactly one of debit_minor / credit_minor must be non-zero."""
    debit = line.debit_minor
    credit = line.credit_minor
    if debit < 0 or credit < 0:
        raise ValueError("journal lines cannot have negative debit or credit values")
    if (debit > 0) == (credit > 0):
        raise ValueError("exactly one of debit_minor / credit_minor must be non-zero")


def assert_single_currency(entry: JournalEntry) -> None:
    """TODO: all lines share a currency, or an explicit FX line is present."""
    if not entry.lines:
        return
    currency = entry.lines[0].currency
    if any(line.currency != currency for line in entry.lines):
        raise ValueError("all journal lines must share a single currency")


def clearing_account_proof(
    *,
    clearing_balance_minor: int,
    captured_unsettled_minor: int,
) -> tuple[bool, int]:
    """TODO: return (proves_out, variance_minor). The self-proving control.

    The Gateway Clearing balance must equal captured-but-unsettled value. A
    non-zero variance is an unreconciled break discovered by the ledger itself,
    independent of the matching engine.
    """
    variance_minor = clearing_balance_minor - captured_unsettled_minor
    return variance_minor == 0, variance_minor
