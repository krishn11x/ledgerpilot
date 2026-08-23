"""ACT node -- DETERMINISTIC CODE. No model call. PLACEHOLDER.

Executes an already-verified, already-permitted proposal. This is the only
place in the agent layer that writes, and it writes through repositories rather
than raw SQL.

Every write is paired with an audit event in the same transaction. A committed
change with no audit trail must be impossible, not merely unlikely.
"""

from __future__ import annotations

from ledgerpilot.agent.state import AgentState


async def act(state: AgentState) -> AgentState:
    """TODO(phase-5): commit the resolution atomically.

    In one transaction:
      1. write the Match (idempotent on content-hashed id)
      2. update Break -> RESOLVED_AUTO
      3. propose the JournalEntry (auto-approve only at autonomy level 3+)
      4. append the audit event with the full evidence chain
    """
    raise NotImplementedError
