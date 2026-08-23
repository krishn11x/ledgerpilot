"""Schema contracts at the boundary. PLACEHOLDER -- signatures only.

Policy: a malformed row must never crash a reconciliation run and must never
be silently dropped. It goes to quarantine with a reason, is counted, and shows
up in the run summary. Silent data loss in a financial control is worse than a
visible failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
        """TODO: accepted / total_rows, guarding divide-by-zero."""
        raise NotImplementedError


def validate_orders(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], ValidationReport]:
    """TODO: required fields, positive amounts, known currency, sane dates."""
    raise NotImplementedError


def validate_gateway_txns(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], ValidationReport]:
    """TODO: as above, plus net == gross - fee - tax internal consistency."""
    raise NotImplementedError


def validate_bank_txns(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], ValidationReport]:
    """TODO: as above, plus direction/sign agreement."""
    raise NotImplementedError
