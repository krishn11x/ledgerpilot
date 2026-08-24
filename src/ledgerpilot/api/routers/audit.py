"""Audit log. SKELETON -- endpoints return 501."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from ledgerpilot.audit.events import query
from ledgerpilot.audit.hashchain import verify_chain as verify_audit_chain

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", summary="Query the hash-chained event log")
def list_events(
    subject_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """TODO(phase-7): paged, filterable, read-only. Never writable over HTTP."""
    events, total = query(subject_id=subject_id, limit=limit, offset=offset)
    return {
        "items": [event.__dict__ for event in events],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/verify", summary="Verify chain integrity")
def verify_chain() -> dict[str, Any]:
    """TODO(phase-7): recompute the chain; report intact + first broken index.

    Rendered as a green/red badge in the UI so an auditor can confirm the log
    has not been edited without reading every entry.
    """
    events, _ = query(limit=10_000)
    intact, first_broken_index = verify_audit_chain(events)
    return {"intact": intact, "first_broken_index": first_broken_index}
