"""INVESTIGATE node -- model call with tools. PLACEHOLDER.

A bounded ReAct loop over the read-only tool surface. Every tool call is
appended to ``state["steps"]``, which serves three purposes at once: the SSE
stream to the UI, the evidence chain in the audit log, and the debugging trace.

Terminates on any of: sufficient findings, step budget exhausted, or token
budget exhausted. The last two route to escalation -- an agent that cannot
converge hands the break to a human rather than guessing.
"""

from __future__ import annotations

from ledgerpilot.agent.state import AgentState


async def investigate(state: AgentState) -> AgentState:
    """TODO(phase-5): one iteration of the tool loop; append to steps."""
    raise NotImplementedError


def should_continue(state: AgentState) -> str:
    """TODO(phase-5): conditional edge -> "investigate" | "hypothesize" | "escalate"."""
    raise NotImplementedError
