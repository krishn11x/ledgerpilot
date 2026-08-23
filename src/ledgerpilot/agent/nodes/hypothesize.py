"""HYPOTHESIZE node -- model call. PLACEHOLDER.

Produces a schema-validated proposal: the match or classification, a confidence
score, an evidence list citing specific record ids, and a controller-language
narrative.

The confidence number must be justified by the cited evidence, not asserted.
That is checked downstream in VERIFY -- a high confidence with thin evidence is
rejected and sent back.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ledgerpilot.agent.state import AgentState
from ledgerpilot.domain.enums import BreakType


class ProposedResolution(BaseModel):
    """The schema the model must emit. PLACEHOLDER -- shape only."""

    break_type: BreakType
    action: str  # match | classify | write_off | escalate
    matched_record_ids: list[str] = Field(default_factory=list)
    amount_explained_minor: int = 0
    residual_minor: int = 0
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    narrative: str = ""
    suggested_journal: dict[str, Any] | None = None


async def hypothesize(state: AgentState) -> AgentState:
    """TODO(phase-5): emit a ProposedResolution into state["proposal"]."""
    raise NotImplementedError
