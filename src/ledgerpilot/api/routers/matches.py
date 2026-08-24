"""Matches."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from ledgerpilot.api.errors import NotFoundError
from ledgerpilot.store.db import session_scope
from ledgerpilot.store.repositories import MatchRepository
from ledgerpilot.store.tables import MatchRow

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("", summary="Query matches")
def list_matches(
    run_id: str | None = Query(default=None),
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Paged list of reconciliation matches."""
    with session_scope() as session:
        statement = select(MatchRow)
        if run_id is not None:
            statement = statement.where(MatchRow.run_id == run_id)
        rows = session.scalars(
            statement.order_by(MatchRow.match_id).offset(offset).limit(limit)
        ).all()
        total = (
            len(MatchRepository(session).for_run(run_id))
            if run_id is not None
            else MatchRepository(session).count()
        )
    items = [row.to_domain().model_dump() for row in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{match_id}", summary="Match detail and score breakdown")
def get_match(match_id: str) -> dict[str, Any]:
    """Legs, method, per-feature score, why it matched."""
    with session_scope() as session:
        match = MatchRepository(session).get(match_id)
    if match is None:
        raise NotFoundError(f"match {match_id!r} not found")
    return match.model_dump()
