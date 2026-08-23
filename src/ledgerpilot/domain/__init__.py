"""Domain layer: pure types.

This package imports **nothing** from the rest of LedgerPilot and has no I/O,
no database, and no LLM. Everything here is a value type or an enum.

That constraint is deliberate: it is what allows the reconciliation engine to
be unit-tested in isolation and to run with the agent layer switched off.
"""

from ledgerpilot.domain.enums import (
    BreakSeverity,
    BreakStatus,
    BreakType,
    DecisionAction,
    DecisionActor,
    ExpectedOutcome,
    JournalEntryStatus,
    MatchMethod,
    MatchStatus,
    ResolutionCategory,
    RunStatus,
    TxnDirection,
)

__all__ = [
    "BreakSeverity",
    "BreakStatus",
    "BreakType",
    "DecisionAction",
    "DecisionActor",
    "ExpectedOutcome",
    "JournalEntryStatus",
    "MatchMethod",
    "MatchStatus",
    "ResolutionCategory",
    "RunStatus",
    "TxnDirection",
]
