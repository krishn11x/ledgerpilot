"""Audit event types and the append API. PLACEHOLDER -- signatures only.

There is exactly one write function, ``append``, and no update or delete. That
asymmetry is the point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from ledgerpilot.domain.enums import DecisionActor


class AuditAction(StrEnum):
    """Every state change that must be explainable after the fact."""

    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RECORDS_INGESTED = "records_ingested"
    ROWS_QUARANTINED = "rows_quarantined"

    MATCH_PROPOSED = "match_proposed"
    MATCH_CONFIRMED = "match_confirmed"
    MATCH_REJECTED = "match_rejected"

    BREAK_DETECTED = "break_detected"
    BREAK_CLASSIFIED = "break_classified"
    BREAK_ESCALATED = "break_escalated"
    BREAK_RESOLVED = "break_resolved"

    AGENT_STEP = "agent_step"
    AGENT_PROPOSAL = "agent_proposal"
    VERIFY_FAILED = "verify_failed"
    BUDGET_EXHAUSTED = "budget_exhausted"

    HUMAN_APPROVED = "human_approved"
    HUMAN_REJECTED = "human_rejected"

    JOURNAL_PROPOSED = "journal_proposed"
    JOURNAL_POSTED = "journal_posted"

    POLICY_CHANGED = "policy_changed"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One immutable link in the chain."""

    event_id: str
    ts: datetime
    actor: DecisionActor
    actor_id: str  # rule name, agent run id, or username
    action: AuditAction
    subject_ids: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    confidence: float | None = None
    inputs_hash: str = ""
    prev_event_hash: str = ""
    event_hash: str = ""

    def compute_hash(self) -> str:
        """TODO: canonical-JSON hash over all fields except event_hash itself."""
        raise NotImplementedError


def append(
    *,
    actor: DecisionActor,
    actor_id: str,
    action: AuditAction,
    subject_ids: list[str] | None = None,
    payload: dict[str, Any] | None = None,
    rationale: str = "",
    confidence: float | None = None,
) -> AuditEvent:
    """TODO: chain onto the last event and persist. The only write path.

    Must run in the same transaction as the change it records, so a committed
    state change with no audit event is impossible.
    """
    raise NotImplementedError


def query(
    *,
    subject_id: str | None = None,
    actor: DecisionActor | None = None,
    action: AuditAction | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditEvent], int]:
    """TODO: read-only paged query for the audit log UI."""
    raise NotImplementedError
