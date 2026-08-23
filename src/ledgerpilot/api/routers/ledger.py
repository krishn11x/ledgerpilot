"""Journal entries and the clearing-account control. SKELETON -- returns 501."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from ledgerpilot.domain.enums import JournalEntryStatus

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("/entries", summary="Proposed and posted journal entries")
def list_entries(
    status: Annotated[JournalEntryStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """TODO(phase-7): paged entries with their lines and rationale."""
    raise NotImplementedError


@router.post("/entries/{entry_id}/approve", summary="Approve a proposed entry")
def approve_entry(entry_id: str) -> dict[str, Any]:
    """TODO(phase-7): approve and post. Re-checks balance before committing."""
    raise NotImplementedError


@router.get("/clearing-proof", summary="Gateway Clearing reconciliation control")
def clearing_proof() -> dict[str, Any]:
    """TODO(phase-7): clearing balance vs captured-but-unsettled.

    The self-proving control. A non-zero variance is an unreconciled break
    found by the ledger itself, independent of the matching engine.
    """
    raise NotImplementedError
