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
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Paged list of reconciliation matches."""
    with session_scope() as session:
        rows = session.scalars(
            select(MatchRow).order_by(MatchRow.match_id).offset(offset).limit(limit)
        ).all()
        total = MatchRepository(session).count()
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
