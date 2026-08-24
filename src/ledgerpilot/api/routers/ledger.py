"""Journal entries and the clearing-account control. SKELETON -- returns 501."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from ledgerpilot.domain.enums import JournalEntryStatus
from ledgerpilot.ledger.balance import clearing_account_proof
from ledgerpilot.store.db import session_scope
from ledgerpilot.store.repositories import GatewayRepository, JournalRepository

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("/entries", summary="Proposed and posted journal entries")
def list_entries(
    status: Annotated[JournalEntryStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """TODO(phase-7): paged entries with their lines and rationale."""
    with session_scope() as session:
        items = JournalRepository(session).all()
    if status is not None:
        items = [item for item in items if item.status == status]
    total = len(items)
    items = items[offset : offset + limit]
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/entries/{entry_id}/approve", summary="Approve a proposed entry")
def approve_entry(entry_id: str) -> dict[str, Any]:
    """TODO(phase-7): approve and post. Re-checks balance before committing."""
    with session_scope() as session:
        repo = JournalRepository(session)
        entry = repo.approve(entry_id, "api")
    if entry is None:
        return {"entry_id": entry_id, "status": "not_found"}
    return entry.model_dump()


@router.get("/clearing-proof", summary="Gateway Clearing reconciliation control")
def clearing_proof() -> dict[str, Any]:
    """TODO(phase-7): clearing balance vs captured-but-unsettled.

    The self-proving control. A non-zero variance is an unreconciled break
    found by the ledger itself, independent of the matching engine.
    """
    with session_scope() as session:
        journal_repo = JournalRepository(session)
        gateway_repo = GatewayRepository(session)
        clearing_balance_minor = journal_repo.clearing_account_balance_minor()
        captured_unsettled_minor = sum(txn.net_minor for txn in gateway_repo.unsettled())
    proves_out, variance_minor = clearing_account_proof(
        clearing_balance_minor=clearing_balance_minor,
        captured_unsettled_minor=captured_unsettled_minor,
    )
    return {
        "proves_out": proves_out,
        "variance_minor": variance_minor,
        "clearing_balance_minor": clearing_balance_minor,
        "captured_unsettled_minor": captured_unsettled_minor,
    }
