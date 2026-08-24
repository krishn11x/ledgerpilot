"""ESCALATE node -- deterministic human-review handoff."""

from __future__ import annotations

from ledgerpilot.agent.state import AgentState


async def escalate(state: AgentState) -> AgentState:
    """Mark the break for human review."""

    state["decision"] = "escalate"
    state["decision_reason"] = "human review required"

    state["escalation"] = {
        "status": "pending_approval",
        "break_id": state.get("break_id"),
        "run_id": state.get("run_id"),
        "reason": state.get(
            "decision_reason",
            "verification or policy failure",
        ),
        "verify_failures": list(
            state.get("verify_failures", [])
        ),
    }

    return state