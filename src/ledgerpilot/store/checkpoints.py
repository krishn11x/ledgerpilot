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

from contextlib import ExitStack
from functools import lru_cache
from typing import Any

from ledgerpilot.config import settings

_resources = ExitStack()


@lru_cache(maxsize=1)
def get_checkpointer() -> Any:
    """Return a process-scoped local checkpointer for demo execution.

    PostgreSQL checkpoint support is supplied by the optional production
    deployment and is intentionally not forced on local SQLite development.
    """
    if settings.is_postgres:
        from langgraph.checkpoint.postgres import PostgresSaver

        checkpointer = _resources.enter_context(
            PostgresSaver.from_conn_string(settings.database_url)
        )
        checkpointer.setup()
        return checkpointer

    from langgraph.checkpoint.memory import MemorySaver

    return MemorySaver()
