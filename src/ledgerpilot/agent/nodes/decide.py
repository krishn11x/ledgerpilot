"""DECIDE node -- deterministic policy gate."""

from __future__ import annotations

from ledgerpilot.agent.state import AgentState
from ledgerpilot.config import settings
from ledgerpilot.domain.enums import BreakType
from ledgerpilot.domain.policy import AutonomyPolicy


async def decide(state: AgentState) -> AgentState:
    """Apply the configured autonomy policy to a verified proposal."""

    confidence = float(state.get("confidence", 0.0))

    ctx = state.get("break_context", {})

    amount = int(
        ctx.get(
            "amount_at_risk_minor",
            state.get("materiality_minor", 0),
        )
    )

    raw_type = state.get(
        "classified_type",
        ctx.get("break_type"),
    )

    break_type = (
    raw_type
    if isinstance(raw_type, BreakType)
    else BreakType(raw_type)
)

    policy = AutonomyPolicy(
        level=int(settings.autonomy_level),
        materiality_threshold_minor=int(
            settings.materiality_threshold_minor
        ),
        min_confidence=float(
            settings.auto_approve_min_confidence
        ),
    )

    if (
        state.get("verified")
        and policy.may_auto_resolve(
            break_type=break_type,
            amount_minor=amount,
            confidence=confidence,
        )
    ):
        state["decision"] = "auto_resolve"
        state["decision_reason"] = (
            "policy permits autonomous resolution"
        )
    else:
        state["decision"] = "escalate"
        state["decision_reason"] = (
            "policy requires human review"
        )

    return state


def decision_route(state: AgentState) -> str:
    """Route the policy decision."""

    if state.get("decision") == "auto_resolve":
        return "act"

    return "escalate"