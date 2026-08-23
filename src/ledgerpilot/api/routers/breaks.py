"""Exception queue -- the controller's inbox. SKELETON -- endpoints return 501.

The most important resource in the API. ``POST /breaks/{id}/decision`` is the
human-in-the-loop hinge: it resumes an interrupted LangGraph run from its
checkpoint, so the agent's reasoning is still attached when the decision is made.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from ledgerpilot.api.schemas import BreakDecisionRequest
from ledgerpilot.domain.enums import BreakStatus, BreakType

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
    raise NotImplementedError


@router.get("/{break_id}", summary="Break detail with full evidence chain")
def get_break(break_id: str) -> dict[str, Any]:
    """TODO(phase-7): break + evidence chain + agent trace + proposed journal.

    This response is what a human reads before approving, so it must include
    contradicting evidence alongside supporting evidence.
    """
    raise NotImplementedError


@router.post("/{break_id}/decision", summary="Approve, reject or reassign")
def decide_break(break_id: str, body: BreakDecisionRequest) -> dict[str, Any]:
    """TODO(phase-7): record the decision and resume the agent graph.

    Must be idempotent and must reject a second decision on an already-decided
    break with 409 -- two reviewers clicking Approve should not post twice.
    """
    raise NotImplementedError


@router.post("/{break_id}/investigate", status_code=202, summary="Run the agent on one break")
def investigate_break(break_id: str) -> dict[str, Any]:
    """TODO(phase-7): manually trigger the agent. Used for the live demo."""
    raise NotImplementedError
