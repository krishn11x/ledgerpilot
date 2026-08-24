"""Server-Sent Events helpers.

SSE rather than WebSockets: progress streaming is unidirectional, so SSE is the
correct fit rather than a compromise. It is a few lines here and native
``EventSource`` in the browser, with no reconnection protocol to design.

Streamed during a run:
    run.progress    pass name, records processed, matches found
    agent.step      each tool call, so reasoning is visible as it happens
    break.detected  new break, appears in the queue live
    run.complete    final counts
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any


def event(name: str, data: dict[str, Any]) -> dict[str, str]:
    """TODO(phase-6): format a dict as an SSE frame."""
    import json

    return {"event": name, "data": json.dumps(data, default=str)}


async def run_progress_stream(run_id: str) -> AsyncIterator[dict[str, str]]:
    """TODO(phase-6): yield SSE frames for a run until it completes.

    Must emit a periodic keepalive comment -- proxies drop idle SSE connections,
    and the agent can legitimately think for a while between steps.
    """
    yield event("run.progress", {"run_id": run_id, "status": "running"})
    yield event("run.complete", {"run_id": run_id, "status": "completed"})
