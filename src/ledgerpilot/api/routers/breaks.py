"""Exception queue -- the controller's inbox.

The most important resource in the API. ``POST /breaks/{id}/decision`` is the
human-in-the-loop hinge: it resumes an interrupted LangGraph run from its
checkpoint, so the agent's reasoning is still attached when the decision is made.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Annotated, Any, cast
from uuid import uuid4

from fastapi import APIRouter, Query

from ledgerpilot.agent.graph import resolve_break
from ledgerpilot.api.errors import ConflictError, NotFoundError
from ledgerpilot.api.schemas import BreakDecisionRequest
from ledgerpilot.audit.events import AuditAction, AuditEvent
from ledgerpilot.audit.hashchain import GENESIS_HASH
from ledgerpilot.audit.trace import build_for_break
from ledgerpilot.domain.enums import BreakStatus, BreakType, DecisionAction, DecisionActor
from ledgerpilot.ledger.balance import assert_balanced
from ledgerpilot.ledger.posting_rules import propose_entry
from ledgerpilot.store.db import session_scope
from ledgerpilot.store.repositories import AuditRepository, BreakRepository, JournalRepository

router = APIRouter(prefix="/breaks", tags=["breaks"])


@router.get("", summary="Query the exception queue")
def list_breaks(
    status: Annotated[BreakStatus | None, Query()] = None,
    break_type: Annotated[BreakType | None, Query()] = None,
    min_amount_minor: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Paged, filtered queue ordered by severity then amount."""
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
    """Break + evidence chain + agent trace + proposed journal."""
    with session_scope() as session:
        brk = BreakRepository(session).get(break_id)
    if brk is None:
        raise NotFoundError(f"break {break_id!r} not found")
    chain = build_for_break(break_id)
    return {"break": brk.model_dump(), "evidence": chain.to_markdown()}


@router.post("/{break_id}/decision", summary="Approve, reject or reassign")
def decide_break(break_id: str, body: BreakDecisionRequest) -> dict[str, Any]:
    """Record human decision, update break status, post journals, and append audit events.

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

        actor_id = body.assignee or "human"
        assignee = body.assignee if body.assignee is not None else brk.assignee

        journal_entry_dict: dict[str, Any] | None = None
        if body.action == DecisionAction.APPROVE:
            new_status = BreakStatus.RESOLVED_MANUAL
            audit_action = AuditAction.HUMAN_APPROVED
        elif body.action == DecisionAction.WRITE_OFF:
            new_status = BreakStatus.WRITTEN_OFF
            audit_action = AuditAction.HUMAN_APPROVED
        elif body.action == DecisionAction.REJECT:
            new_status = BreakStatus.REJECTED
            audit_action = AuditAction.HUMAN_REJECTED
        elif body.action == DecisionAction.ESCALATE:
            new_status = BreakStatus.ESCALATED
            audit_action = AuditAction.BREAK_ESCALATED
        elif body.action == DecisionAction.REASSIGN:
            new_status = brk.status
            audit_action = AuditAction.BREAK_CLASSIFIED
        elif body.action == DecisionAction.COMMENT:
            new_status = brk.status
            audit_action = AuditAction.HUMAN_APPROVED
        else:
            new_status = brk.status
            audit_action = AuditAction.HUMAN_APPROVED

        if body.action in (DecisionAction.APPROVE, DecisionAction.WRITE_OFF):
            entry = propose_entry(brk)
            if entry is not None:
                assert_balanced(entry)
                journal_repo = JournalRepository(session)
                journal_repo.propose(entry)
                approved_entry = journal_repo.approve(entry.entry_id, approved_by=actor_id)
                if approved_entry is not None:
                    journal_entry_dict = approved_entry.model_dump()
                else:
                    journal_entry_dict = entry.model_dump()

        updated = brk.model_copy(
            update={"status": new_status, "assignee": assignee}
        )
        repo.upsert(updated)

        audit_repo = AuditRepository(session)
        prev_hash = audit_repo.latest_hash()
        if not prev_hash or prev_hash == "0" * 64:
            prev_hash = GENESIS_HASH

        event = AuditEvent(
            event_id=f"AEV-{uuid4().hex[:16]}",
            ts=datetime.now(UTC),
            actor=DecisionActor.HUMAN,
            actor_id=actor_id,
            action=audit_action,
            subject_ids=[break_id],
            payload={
                "break_id": break_id,
                "decision": body.action,
                "action": body.action,
                "note": body.note,
                "assignee": assignee,
                "status": new_status,
            },
            rationale=body.note or f"Human decision: {body.action}",
            prev_event_hash=prev_hash,
        )
        event = replace(event, event_hash=event.compute_hash())
        audit_repo.append(event)

    res: dict[str, Any] = {
        "break_id": break_id,
        "status": new_status,
        "decision": body.action,
        "action": body.action,
        "note": body.note,
        "assignee": assignee,
    }
    if journal_entry_dict is not None:
        res["journal_entry"] = journal_entry_dict

    return res


@router.post("/{break_id}/investigate", status_code=202, summary="Run the agent on one break")
def investigate_break(break_id: str) -> dict[str, Any]:
    """Manually trigger the agent. Used for the live demo."""
    return cast(
        dict[str, Any],
        __import__("asyncio").run(resolve_break(break_id, run_id=f"RUN-{break_id}")),
    )
