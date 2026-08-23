"""LangGraph state machine assembly. PLACEHOLDER -- signatures only.

Why LangGraph rather than a plain tool-use loop: the graph gives durable
checkpointed state, so ``interrupt()`` at the DECIDE node lets a break wait in
the exception queue for hours and then resume with its reasoning intact. That
is the human-in-the-loop story, and hand-rolling it correctly is more work than
adopting it.
"""

from __future__ import annotations

from typing import Any


def build_graph(*, checkpointer: Any | None = None) -> Any:
    """TODO(phase-5): assemble and compile the agent graph.

    Wiring:
        START        -> triage
        triage       -> investigate
        investigate  -> investigate   (tool loop, bounded by agent_max_steps)
        investigate  -> hypothesize   (when findings are sufficient)
        hypothesize  -> verify
        verify       -> hypothesize   (on failure, bounded by agent_max_retries)
        verify       -> decide        (on success)
        decide       -> act           (policy permits autonomous resolution)
        decide       -> escalate      (interrupt -> PENDING_APPROVAL)
        act          -> END
        escalate     -> END
    """
    raise NotImplementedError


async def resolve_break(break_id: str, *, run_id: str) -> dict[str, Any]:
    """TODO(phase-5): run one break through the graph; return final state."""
    raise NotImplementedError


async def resume_break(break_id: str, *, action: str, actor: str, note: str = "") -> dict[str, Any]:
    """TODO(phase-5): resume an interrupted graph after a human decision.

    Called by ``POST /breaks/{id}/decision``. Loads the checkpoint, injects the
    human decision, and continues to ACT or terminal rejection.
    """
    raise NotImplementedError
