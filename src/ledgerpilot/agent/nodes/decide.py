"""DECIDE node -- DETERMINISTIC CODE. No model call. PLACEHOLDER.

The policy gate. Applies ``domain.policy.AutonomyPolicy`` to a *verified*
proposal and routes to ACT or ESCALATE.

Intentionally boring: a handful of comparisons against configured thresholds.
Boring is the requirement -- this is the code that decides whether money moves
without a human, so it must be readable in one sitting and auditable line by
line.
"""

from __future__ import annotations

from ledgerpilot.agent.state import AgentState


async def decide(state: AgentState) -> AgentState:
    """TODO(phase-5): set decision + decision_reason from policy.

    Gate conditions, all required for autonomous resolution:
      * state["verified"] is True
      * autonomy_level >= AUTO_CLEAR
      * confidence >= auto_approve_min_confidence
      * amount_at_risk < materiality_threshold
      * break type is not inherently human-only (duplicates, chargebacks)
    """
    raise NotImplementedError


def decision_route(state: AgentState) -> str:
    """TODO(phase-5): conditional edge -> "act" | "escalate"."""
    raise NotImplementedError
