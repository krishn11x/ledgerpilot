"""LangGraph state machine assembly.

Why LangGraph rather than a plain tool-use loop: the graph gives durable
checkpointed state, so ``interrupt()`` at the DECIDE node lets a break wait in
the exception queue for hours and then resume with its reasoning intact. That
is the human-in-the-loop story, and hand-rolling it correctly is more work than
adopting it.
"""

from __future__ import annotations

from typing import Any, cast

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from ledgerpilot.agent.nodes.act import act
from ledgerpilot.agent.nodes.decide import decide, decision_route
from ledgerpilot.agent.nodes.escalate import escalate
from ledgerpilot.agent.nodes.hypothesize import hypothesize
from ledgerpilot.agent.nodes.investigate import investigate, should_continue
from ledgerpilot.agent.nodes.triage import triage
from ledgerpilot.agent.nodes.verify import verification_route, verify
from ledgerpilot.agent.state import AgentState
from ledgerpilot.store.checkpoints import get_checkpointer
from ledgerpilot.store.db import session_scope
from ledgerpilot.store.repositories import BreakRepository


def build_graph(*, checkpointer: Any | None = None) -> Any:
    """Assemble and compile the agent graph.

    Wiring:
        START        -> triage
        triage       -> investigate
        investigate  -> hypothesize   (when findings are sufficient)
        investigate  -> escalate      (when steps_used >= max steps)
        hypothesize  -> verify
        verify       -> hypothesize   (on failure, bounded by agent_max_retries)
        verify       -> decide        (on success)
        decide       -> act           (policy permits autonomous resolution)
        decide       -> escalate      (policy requires human review)
        act          -> END
        escalate     -> END
    """
    builder = StateGraph(AgentState)

    builder.add_node("triage", triage)
    builder.add_node("investigate", investigate)
    builder.add_node("hypothesize", hypothesize)
    builder.add_node("verify", verify)
    builder.add_node("decide", decide)
    builder.add_node("act", act)
    builder.add_node("escalate", escalate)

    builder.add_edge(START, "triage")
    builder.add_edge("triage", "investigate")
    builder.add_conditional_edges("investigate", should_continue)
    builder.add_edge("hypothesize", "verify")
    builder.add_conditional_edges("verify", verification_route)
    builder.add_conditional_edges("decide", decision_route)
    builder.add_edge("act", END)
    builder.add_edge("escalate", END)

    return builder.compile(checkpointer=checkpointer)


async def resolve_break(break_id: str, *, run_id: str) -> dict[str, Any]:
    """Run one break through the graph; return final state."""
    with session_scope() as session:
        brk = BreakRepository(session).get(break_id)
    if brk is None:
        raise KeyError(f"unknown break {break_id}")
    state: AgentState = {
        "break_id": break_id,
        "run_id": run_id,
            "break_context": {
            "break_id": break_id,
            "break_type": brk.break_type,
            "amount_at_risk_minor": brk.amount_at_risk_minor,
            "currency": brk.currency,
            "narration": brk.narrative or brk.summary,
            "subject_ids": [leg.record_id for leg in brk.legs],
            "break_obj": brk,
                "checkpointed": True,
        },
        "steps": [],
        "tokens_used": 0,
        "steps_used": 0,
        "retry_count": 0,
    }
    graph = build_graph(checkpointer=get_checkpointer())
    result = await graph.ainvoke(
        state,
        config={"configurable": {"thread_id": break_id}},
    )
    return cast(dict[str, Any], result)


async def resume_break(break_id: str, *, action: str, actor: str, note: str = "") -> dict[str, Any]:
    """Resume an interrupted graph after a human decision.

    Called by ``POST /breaks/{id}/decision``. Loads the checkpoint, injects the
    human decision, and continues to ACT or terminal rejection.
    """
    graph = build_graph(checkpointer=get_checkpointer())
    result = await graph.ainvoke(
        Command(resume={"action": action, "note": note, "actor": actor}),
        config={"configurable": {"thread_id": break_id}},
    )
    return cast(dict[str, Any], result)
