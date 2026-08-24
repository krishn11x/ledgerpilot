"""ACT node -- execute an already verified autonomous resolution."""

from __future__ import annotations

from ledgerpilot.agent.state import AgentState
from ledgerpilot.ledger.posting_rules import propose_entry


async def act(state: AgentState) -> AgentState:
    """Apply the verified autonomous resolution."""

    if state.get("decision") != "auto_resolve":
        return state

    ctx = state.get("break_context", {})
    break_obj = ctx.get("break_obj")

    if break_obj is None:
        state["decision"] = "escalate"
        state["decision_reason"] = (
            "break object unavailable for autonomous action"
        )
        return state

    entry = propose_entry(break_obj)

    state["executed_journal"] = (
        entry.model_dump() if entry is not None else None
    )

    state["decision"] = "auto_resolve"
    state["decision_reason"] = "verified proposal executed"

    return state