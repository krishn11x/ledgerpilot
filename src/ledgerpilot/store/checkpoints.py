"""LangGraph checkpoint persistence.

PLACEHOLDER -- signatures only.

Why this matters architecturally: when the agent hits a break it is not
allowed to auto-resolve, LangGraph ``interrupt()``s and the graph state is
checkpointed here. The break then surfaces in the exception queue as
PENDING_APPROVAL. When a human clicks Approve hours later, the graph resumes
from this checkpoint with its full reasoning intact.

That is what makes the human-in-the-loop story real rather than cosmetic: the
agent's evidence chain survives the wait and stays attached to the decision.

    SQLite dev   -> langgraph.checkpoint.sqlite.SqliteSaver
    PostgreSQL   -> langgraph.checkpoint.postgres.PostgresSaver
"""

from __future__ import annotations

from typing import Any

from ledgerpilot.config import settings


def get_checkpointer() -> Any:
    """TODO(phase-5): return a LangGraph checkpointer for the configured DB.

    Must select PostgresSaver when ``settings.is_postgres`` and SqliteSaver
    otherwise, and must run its own ``setup()`` migration on first use.
    """
    raise NotImplementedError(
        f"checkpointer not implemented (dialect: "
        f"{'postgres' if settings.is_postgres else 'sqlite'})"
    )
