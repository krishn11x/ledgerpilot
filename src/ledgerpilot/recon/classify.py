"""Break classification. PLACEHOLDER -- signatures only.

Turns "these records did not match" into a typed, explained break. This is the
module that produces the product: the taxonomy in
``ledgerpilot.domain.enums.BreakType``.

Deterministic classification runs first and covers the known taxonomy. Anything
it cannot place becomes UNCLASSIFIED and is handed to the agent, which performs
open-set classification -- the honest split between what rules do well and what
an LLM does well.
"""

from __future__ import annotations

from ledgerpilot.domain.enums import BreakType
from ledgerpilot.domain.models import Break


def classify_unmatched_order(order_id: str) -> BreakType:
    """TODO: MISSING_IN_GATEWAY, or TIMING_DIFFERENCE if inside settlement lag."""
    raise NotImplementedError


def classify_unmatched_gateway_txn(txn_id: str) -> BreakType:
    """TODO: ORPHAN_PAYMENT / UNSETTLED / TIMING_DIFFERENCE."""
    raise NotImplementedError


def classify_unmatched_bank_txn(bank_txn_id: str) -> BreakType:
    """TODO: UNIDENTIFIED_CREDIT, or a debit-side classification."""
    raise NotImplementedError


def classify_amount_discrepancy(expected_minor: int, actual_minor: int) -> BreakType:
    """TODO: SHORT_PAYMENT / OVERPAYMENT / FEE_VARIANCE / FX_VARIANCE.

    Distinguishing fee variance from short payment requires the fee schedule:
    if the gap equals the expected fee, it is a fee posting issue, not a
    customer underpayment. Getting this wrong sends the break to the wrong team.
    """
    raise NotImplementedError


def detect_duplicates(order_id: str) -> list[str]:
    """TODO: multiple captures against one order -- always CRITICAL severity."""
    raise NotImplementedError


def build_break(break_type: BreakType, **kwargs: object) -> Break:
    """TODO: assemble a Break with severity, summary line and evidence."""
    raise NotImplementedError
