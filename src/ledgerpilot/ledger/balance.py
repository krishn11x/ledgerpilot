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
    raise NotImplementedError


def assert_single_sided(line: JournalLine) -> None:
    """TODO: exactly one of debit_minor / credit_minor must be non-zero."""
    raise NotImplementedError


def assert_single_currency(entry: JournalEntry) -> None:
    """TODO: all lines share a currency, or an explicit FX line is present."""
    raise NotImplementedError


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
    raise NotImplementedError
