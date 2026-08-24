"""Exception queue -- the controller's inbox. SKELETON -- endpoints return 501.

The most important resource in the API. ``POST /breaks/{id}/decision`` is the
human-in-the-loop hinge: it resumes an interrupted LangGraph run from its
checkpoint, so the agent's reasoning is still attached when the decision is made.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from ledgerpilot.agent.graph import resolve_break
from ledgerpilot.api.errors import ConflictError, NotFoundError
from ledgerpilot.api.schemas import BreakDecisionRequest
from ledgerpilot.audit.trace import build_for_break
from ledgerpilot.domain.enums import BreakStatus, BreakType, DecisionAction
from ledgerpilot.store.db import session_scope
from ledgerpilot.store.repositories import BreakRepository

router = APIRouter(prefix="/breaks", tags=["breaks"])


@router.get("", summary="Query the exception queue")
def list_breaks(
    status: Annotated[BreakStatus | None, Query()] = None,
    break_type: Annotated[BreakType | None, Query()] = None,
    min_amount_minor: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """TODO(phase-7): paged, filtered queue ordered by severity then amount."""
    with session_scope() as session:
        items, total = BreakRepository(session).query(
            status=status,
            break_type=break_type,
            min_amount_minor=min_amount_minor,
            limit=limit,
            offset=offset,
        )
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{break_id}", summary="Break detail with full evidence chain")
def get_break(break_id: str) -> dict[str, Any]:
    """TODO(phase-7): break + evidence chain + agent trace + proposed journal.

    This response is what a human reads before approving, so it must include
    contradicting evidence alongside supporting evidence.
    """
    with session_scope() as session:
        brk = BreakRepository(session).get(break_id)
    if brk is None:
        raise NotFoundError(f"break {break_id!r} not found")
    chain = build_for_break(break_id)
    return {"break": brk.model_dump(), "evidence": chain.to_markdown()}


@router.post("/{break_id}/decision", summary="Approve, reject or reassign")
def decide_break(break_id: str, body: BreakDecisionRequest) -> dict[str, Any]:
    """TODO(phase-7): record the decision and resume the agent graph.

    Must be idempotent and must reject a second decision on an already-decided
    break with 409 -- two reviewers clicking Approve should not post twice.
    """
    with session_scope() as session:
        repo = BreakRepository(session)
        brk = repo.get(break_id)
        if brk is None:
            raise NotFoundError(f"break {break_id!r} not found")
        if brk.status not in (
            BreakStatus.OPEN,
            BreakStatus.INVESTIGATING,
            BreakStatus.PENDING_APPROVAL,
        ):
            raise ConflictError(f"break {break_id!r} already decided")
        if body.action == DecisionAction.APPROVE:
            updated = brk.model_copy(
                update={"status": BreakStatus.RESOLVED_MANUAL, "assignee": body.assignee}
            )
        elif body.action == DecisionAction.REJECT:
            updated = brk.model_copy(
                update={"status": BreakStatus.REJECTED, "assignee": body.assignee}
            )
        else:
            updated = brk.model_copy(
                update={"status": BreakStatus.ESCALATED, "assignee": body.assignee}
            )
        repo.upsert(updated)
    return {"break_id": break_id, "status": updated.status, "note": body.note}


@router.post("/{break_id}/investigate", status_code=202, summary="Run the agent on one break")
def investigate_break(break_id: str) -> dict[str, Any]:
    """TODO(phase-7): manually trigger the agent. Used for the live demo."""
    return __import__("asyncio").run(resolve_break(break_id, run_id=f"RUN-{break_id}"))
