"""INVESTIGATE node -- bounded read-only evidence gathering."""

from __future__ import annotations

from ledgerpilot.agent.state import AgentState
from ledgerpilot.agent.tools import parse_narration
from ledgerpilot.config import settings


async def investigate(state: AgentState) -> AgentState:
    """Gather deterministic evidence without modifying ledger state."""

    ctx = state.get("break_context", {})
    steps = list(state.get("steps", []))

    narration = str(ctx.get("narration", ""))

    findings = list(state.get("findings", []))

    if narration:
        parsed = parse_narration(narration)

        findings.append(
            {
                "node": "investigate",
                "tool": "parse_narration",
                "input": narration,
                "output": parsed,
                "tokens": 10,
            }
        )

    state["steps"] = steps + [
        {
            "node": "investigate",
            "tool": "parse_narration",
            "output": findings[-1]["output"] if findings else {},
        }
    ]

    state["findings"] = findings
    state["steps_used"] = int(state.get("steps_used", 0)) + 1
    state["tokens_used"] = int(state.get("tokens_used", 0)) + 10

    return state


def should_continue(state: AgentState) -> str:
    """Route to hypothesis after bounded investigation."""

    if state.get("steps_used", 0) >= settings.agent_max_steps:
        return "escalate"

    return "hypothesize"