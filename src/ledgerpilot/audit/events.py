"""Audit event types and the append API.

There is exactly one write function, ``append``, and no update or delete.
That asymmetry is intentional: audit events are append-only and immutable.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from ledgerpilot.audit.hashchain import GENESIS_HASH, hash_event
from ledgerpilot.domain.enums import DecisionActor
from ledgerpilot.store.db import session_scope
from ledgerpilot.store.tables import AuditEventRow


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
    """One immutable link in the audit chain."""

    event_id: str
    ts: datetime
    actor: DecisionActor
    actor_id: str
    action: AuditAction
    subject_ids: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    confidence: float | None = None
    inputs_hash: str = ""
    prev_event_hash: str = ""
    event_hash: str = ""

    def compute_hash(self) -> str:
        """Compute the canonical event hash excluding ``event_hash`` itself."""
        payload = {
            "event_id": self.event_id,
            "ts": self.ts,
            "actor": self.actor,
            "actor_id": self.actor_id,
            "action": self.action,
            "subject_ids": self.subject_ids,
            "payload": self.payload,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "inputs_hash": self.inputs_hash,
            "prev_event_hash": self.prev_event_hash,
        }

        return hash_event(payload, self.prev_event_hash)


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
    """Append and persist one immutable audit event."""

    subjects = list(subject_ids or [])
    data = dict(payload or {})

    event = AuditEvent(
        event_id=f"AEV-{uuid4().hex[:16]}",
        ts=datetime.now(UTC),
        actor=actor,
        actor_id=actor_id,
        action=action,
        subject_ids=subjects,
        payload=data,
        rationale=rationale,
        confidence=confidence,
        prev_event_hash=GENESIS_HASH,
    )

    with session_scope() as session:
        last = (
            session.query(AuditEventRow)
            .order_by(AuditEventRow.sequence_number.desc())
            .first()
        )

        if last is not None:
            event = replace(
                event,
                prev_event_hash=last.hash,
            )

        event = replace(
            event,
            event_hash=event.compute_hash(),
        )

        sequence_number = (
            last.sequence_number + 1
            if last is not None
            else 1
        )

        row = AuditEventRow(
            event_id=event.event_id,
            sequence_number=sequence_number,
            timestamp=event.ts,
            event_type=event.action.value,
            actor=event.actor,
            target_type=subjects[0] if subjects else "",
            target_id=subjects[0] if subjects else "",
            payload={
                "actor_id": actor_id,
                "subject_ids": subjects,
                "payload": data,
                "rationale": rationale,
                "confidence": confidence,
            },
            prev_hash=event.prev_event_hash,
            hash=event.event_hash,
        )

        session.add(row)

    return event


def query(
    *,
    subject_id: str | None = None,
    actor: DecisionActor | None = None,
    action: AuditAction | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[AuditEvent], int]:
    """Read-only paginated audit-log query."""

    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    if offset < 0:
        raise ValueError("offset cannot be negative")

    with session_scope() as session:
        statement = session.query(AuditEventRow)

        if subject_id is not None:
            statement = statement.filter(
                AuditEventRow.target_id == subject_id
            )

        if actor is not None:
            statement = statement.filter(
                AuditEventRow.actor == actor
            )

        if action is not None:
            statement = statement.filter(
                AuditEventRow.event_type == action.value
            )

        total = statement.count()

        rows = (
            statement
            .order_by(AuditEventRow.sequence_number)
            .offset(offset)
            .limit(limit)
            .all()
        )

        events = [
            AuditEvent(
                event_id=row.event_id,
                ts=row.timestamp,
                actor=row.actor,
                actor_id=row.payload.get("actor_id", ""),
                action=AuditAction(row.event_type),
                subject_ids=list(
                    row.payload.get("subject_ids", [])
                ),
                payload=dict(
                    row.payload.get("payload", {})
                ),
                rationale=row.payload.get("rationale", ""),
                confidence=row.payload.get("confidence"),
                prev_event_hash=row.prev_hash,
                event_hash=row.hash,
            )
            for row in rows
        ]

        return events, total