"""VERIFY node -- DETERMINISTIC CODE. No model call. PLACEHOLDER.

The most important node in the graph, and it contains no AI at all.

It independently re-derives every number the model claimed. If the arithmetic
does not reproduce, the proposal is rejected and sent back to HYPOTHESIZE with
the specific failures attached -- up to ``agent_max_retries``, after which the
break escalates.

Explicitly **not** a second LLM call. Self-grading by another model instance
correlates its errors with the first and provides false assurance. Arithmetic
the model cannot influence is the only check worth having here.
"""

from __future__ import annotations

from ledgerpilot.agent.state import AgentState


async def verify(state: AgentState) -> AgentState:
    """TODO(phase-5): run every check; set verified + verify_failures.

    Checks to implement:
      1. grounding      -- every cited record id exists
      2. arithmetic     -- amounts re-derive exactly in minor units
      3. no double-use  -- cited records are not already matched elsewhere
      4. currency       -- no cross-currency claim without an FX line
      5. evidence floor -- confidence >= 0.9 requires at least N cited records
      6. balance        -- any suggested journal passes assert_balanced
    """
    raise NotImplementedError


def verification_route(state: AgentState) -> str:
    """TODO(phase-5): conditional edge -> "decide" | "hypothesize" | "escalate"."""
    raise NotImplementedError
