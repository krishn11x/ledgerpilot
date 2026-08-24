"""Audit log."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from ledgerpilot.audit.events import AuditEvent, query
from ledgerpilot.audit.hashchain import verify_chain as verify_audit_chain

router = APIRouter(prefix="/audit", tags=["audit"])


def _serialize_event(e: AuditEvent) -> dict[str, Any]:
    return {
        "event_id": e.event_id,
        "ts": e.ts.isoformat() if e.ts else "",
        "actor": e.actor.value if hasattr(e.actor, "value") else str(e.actor),
        "actor_id": e.actor_id,
        "action": e.action.value if hasattr(e.action, "value") else str(e.action),
        "subject_ids": list(e.subject_ids),
        "payload": dict(e.payload),
        "rationale": e.rationale,
        "confidence": e.confidence,
        "inputs_hash": e.inputs_hash,
        "prev_event_hash": e.prev_event_hash,
        "event_hash": e.event_hash,
    }


@router.get("", summary="Query the hash-chained event log")
def list_events(
    subject_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Paged, filterable, read-only event log."""
    events, total = query(subject_id=subject_id, limit=limit, offset=offset)
    return {
        "items": [_serialize_event(event) for event in events],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/verify", summary="Verify chain integrity")
def verify_chain() -> dict[str, Any]:
    """Recompute the chain; report intact + first broken index."""
    events, _ = query(limit=10_000)
    intact, first_broken_index = verify_audit_chain(events)
    return {"intact": intact, "first_broken_index": first_broken_index}
