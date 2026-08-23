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

import uuid
from datetime import UTC, datetime
from typing import Any

from ledgerpilot.domain.enums import BreakSeverity, BreakStatus, BreakType
from ledgerpilot.domain.models import Break, GatewayTxn, MatchLeg


def classify_unmatched_order(order_id: str) -> BreakType:
    """Classify an unmatched order: MISSING_IN_GATEWAY."""
    return BreakType.MISSING_IN_GATEWAY


def classify_unmatched_gateway_txn(txn: GatewayTxn | str) -> BreakType:
    """Classify an unmatched gateway txn: ORPHAN_PAYMENT / UNSETTLED."""
    if isinstance(txn, GatewayTxn):
        if txn.payout_id is None:
            return BreakType.UNSETTLED
        if txn.order_ref is None:
            return BreakType.ORPHAN_PAYMENT
    return BreakType.ORPHAN_PAYMENT


def classify_unmatched_bank_txn(bank_txn_id: str) -> BreakType:
    """Classify an unmatched bank txn: UNIDENTIFIED_CREDIT."""
    return BreakType.UNIDENTIFIED_CREDIT


def classify_amount_discrepancy(
    expected_minor: int, actual_minor: int, is_fee: bool = False
) -> BreakType:
    """Classify amount discrepancies into SHORT_PAYMENT / FEE_VARIANCE / AMOUNT_MISMATCH."""
    if is_fee:
        return BreakType.FEE_VARIANCE
    if actual_minor < expected_minor:
        return BreakType.SHORT_PAYMENT
    return BreakType.AMOUNT_MISMATCH


def detect_duplicates(gateway_txns: list[GatewayTxn]) -> list[str]:
    """Detect multiple captures against one order."""
    counts: dict[str, list[str]] = {}
    for t in gateway_txns:
        if t.order_ref:
            counts.setdefault(t.order_ref, []).append(t.txn_id)
    duplicates: list[str] = []
    for _, txn_ids in counts.items():
        if len(txn_ids) > 1:
            duplicates.extend(txn_ids)
    return duplicates


def _severity_for(break_type: BreakType) -> BreakSeverity:
    if break_type in (
        BreakType.DUPLICATE_PAYMENT,
        BreakType.CHARGEBACK,
        BreakType.REFUND_UNAPPLIED,
    ):
        return BreakSeverity.HIGH
    if break_type in (
        BreakType.AMOUNT_MISMATCH,
        BreakType.PAYOUT_MISMATCH,
        BreakType.FEE_VARIANCE,
        BreakType.SHORT_PAYMENT,
        BreakType.MISSING_IN_GATEWAY,
        BreakType.ORPHAN_PAYMENT,
    ):
        return BreakSeverity.MEDIUM
    return BreakSeverity.LOW


def build_break(
    break_type: BreakType,
    *,
    amount_at_risk_minor: int,
    currency: str = "INR",
    legs: list[MatchLeg] | None = None,
    detected_by: str = "recon_engine",
    summary: str = "",
    evidence: list[dict[str, Any]] | None = None,
    break_id: str | None = None,
    severity: BreakSeverity | None = None,
    status: BreakStatus = BreakStatus.OPEN,
    **kwargs: object,
) -> Break:
    """Assemble a Break with severity, summary, and evidence."""
    b_id = break_id or f"BRK-{uuid.uuid4().hex[:8]}"
    b_sev = severity or _severity_for(break_type)
    b_summary = summary or f"{break_type.value.replace('_', ' ').title()} break detected"

    return Break(
        break_id=b_id,
        break_type=break_type,
        severity=b_sev,
        status=status,
        amount_at_risk_minor=amount_at_risk_minor,
        currency=currency,
        legs=legs or [],
        detected_by=detected_by,
        detected_at=datetime.now(UTC),
        summary=b_summary,
        evidence=evidence or [],
    )
