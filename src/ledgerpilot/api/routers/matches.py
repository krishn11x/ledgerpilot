"""Matches. SKELETON -- endpoints return 501."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ledgerpilot.api.errors import NotFoundError
from ledgerpilot.store.db import session_scope
from ledgerpilot.store.repositories import MatchRepository

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/{match_id}", summary="Match detail and score breakdown")
def get_match(match_id: str) -> dict[str, Any]:
    """TODO(phase-7): legs, method, per-feature score, why it matched.

    The per-feature breakdown is the point: "confidence 0.87" alone is not
    reviewable, "amount exact, date 1 day off, narration 0.79" is.
    """
    with session_scope() as session:
        match = MatchRepository(session).get(match_id)
    if match is None:
        raise NotFoundError(f"match {match_id!r} not found")
    return match.model_dump()
