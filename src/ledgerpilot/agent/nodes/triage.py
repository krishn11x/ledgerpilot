"""TRIAGE node -- deterministic routing."""

from __future__ import annotations

from ledgerpilot.agent.state import AgentState
from ledgerpilot.config import settings
from ledgerpilot.domain.enums import BreakType
from ledgerpilot.domain.policy import severity_for


async def triage(state: AgentState) -> AgentState:
    """Classify the break and assess materiality."""

    ctx = state.get("break_context", {})
    raw_type = ctx.get("break_type")

    if isinstance(raw_type, BreakType):
        break_type = raw_type
    else:
        break_type = BreakType(raw_type)

    amount = int(ctx.get("amount_at_risk_minor", 0))

    severity = severity_for(
        break_type,
        amount,
        settings.materiality_threshold_minor,
    )

    state["classified_type"] = break_type.value
    state["materiality_minor"] = amount
    state["triage_rationale"] = (
        f"classified {break_type.value} at severity {severity.value}"
    )

    return state