"""Matches. SKELETON -- endpoints return 501."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("/{match_id}", summary="Match detail and score breakdown")
def get_match(match_id: str) -> dict[str, Any]:
    """TODO(phase-7): legs, method, per-feature score, why it matched.

    The per-feature breakdown is the point: "confidence 0.87" alone is not
    reviewable, "amount exact, date 1 day off, narration 0.79" is.
    """
    raise NotImplementedError
