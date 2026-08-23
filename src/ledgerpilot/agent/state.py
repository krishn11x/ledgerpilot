"""Agent graph state. PLACEHOLDER -- shape only.

The state object is also the audit record: every field here ends up in the
break's evidence chain, which is why it carries the full step history rather
than just the latest conclusion. When a human approves a decision three hours
later, this is what they are shown.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from ledgerpilot.domain.enums import BreakType


class AgentStep(TypedDict):
    """One observable action, for the evidence chain and the SSE stream."""

    node: str
    tool: str | None
    input: dict[str, Any]
    output: dict[str, Any]
    tokens: int


def _append(left: list[Any], right: list[Any]) -> list[Any]:
    """LangGraph reducer: accumulate rather than overwrite."""
    return left + right


class AgentState(TypedDict, total=False):
    """State threaded through the graph.

    ``steps`` uses an append reducer so history accumulates across nodes; every
    other field is last-write-wins.
    """

    # -- Input ---------------------------------------------------------------
    break_id: str
    run_id: str
    break_context: dict[str, Any]

    # -- TRIAGE output -------------------------------------------------------
    classified_type: BreakType
    materiality_minor: int
    triage_rationale: str

    # -- INVESTIGATE output --------------------------------------------------
    steps: Annotated[list[AgentStep], _append]
    findings: dict[str, Any]

    # -- HYPOTHESIZE output --------------------------------------------------
    proposal: dict[str, Any]
    confidence: float
    evidence: list[dict[str, Any]]
    narrative: str

    # -- VERIFY output (written by deterministic code) ------------------------
    verified: bool
    verify_failures: list[str]
    retry_count: int

    # -- DECIDE output -------------------------------------------------------
    decision: Literal["auto_resolve", "auto_post", "escalate", "reject"]
    decision_reason: str

    # -- Budget tracking -----------------------------------------------------
    tokens_used: int
    steps_used: int
