"""ESCALATE node -- DETERMINISTIC CODE. No model call. PLACEHOLDER.

Hands the break to a human via LangGraph ``interrupt()``. The graph state is
checkpointed, the break moves to PENDING_APPROVAL, and the run continues with
other breaks.

The escalation is not a dead end -- it is a suspended computation. When someone
approves via ``POST /breaks/{id}/decision``, the graph resumes from this exact
point with the agent's full reasoning still attached, and proceeds to ACT.
"""

from __future__ import annotations

from ledgerpilot.agent.state import AgentState


async def escalate(state: AgentState) -> AgentState:
    """TODO(phase-5): checkpoint and interrupt.

    Steps:
      1. persist the agent's findings and narrative onto the Break
      2. set Break.status = PENDING_APPROVAL, severity from policy
      3. append an audit event recording *why* it escalated
      4. call interrupt() so the graph suspends resumably
    """
    raise NotImplementedError
