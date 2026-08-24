"""HYPOTHESIZE node -- deterministic proposal construction."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ledgerpilot.agent.state import AgentState
from ledgerpilot.domain.enums import BreakType
from ledgerpilot.ledger.posting_rules import propose_entry


class ProposedResolution(BaseModel):
    """Schema for the proposed resolution."""

    break_type: BreakType
    action: str
    matched_record_ids: list[str] = Field(default_factory=list)
    amount_explained_minor: int = 0
    residual_minor: int = 0
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    narrative: str = ""
    suggested_journal: dict[str, Any] | None = None


async def hypothesize(state: AgentState) -> AgentState:
    """Build a deterministic, schema-valid proposal."""

    ctx = state.get("break_context", {})
    break_obj = ctx.get("break_obj")

    raw_type = ctx.get("break_type")

    if isinstance(raw_type, BreakType):
        break_type = raw_type
    else:
        break_type = BreakType(raw_type)

    amount = int(ctx.get("amount_at_risk_minor", 0))

    subject_ids = list(ctx.get("subject_ids", []))

    journal = None

    if break_obj is not None:
        proposed = propose_entry(break_obj)

        if proposed is not None:
            journal = proposed.model_dump()

    if break_type in {
        BreakType.SHORT_PAYMENT,
        BreakType.CHARGEBACK,
    }:
        action = "write_off"
    elif break_type in {
        BreakType.TIMING_DIFFERENCE,
        BreakType.UNSETTLED,
    }:
        action = "classify"
    else:
        action = "classify"

    confidence = 0.95 if break_obj is not None else 0.0

    evidence = [
        {
            "kind": "record",
            "label": str(ctx.get("break_id", "")),
            "detail": ctx,
        }
    ]

    proposal = ProposedResolution(
        break_type=break_type,
        action=action,
        matched_record_ids=subject_ids,
        amount_explained_minor=amount,
        residual_minor=0,
        confidence=confidence,
        evidence=evidence,
        narrative=f"Resolved {break_type.value}",
        suggested_journal=journal,
    )

    state["proposal"] = proposal.model_dump()
    state["confidence"] = proposal.confidence
    state["evidence"] = proposal.evidence
    state["narrative"] = proposal.narrative

    return state