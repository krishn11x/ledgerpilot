"""TRIAGE node -- model call. PLACEHOLDER.

Classifies a residual break into the taxonomy and assesses materiality. Cheap
model (Sonnet), single call, no tools. Its job is routing, not resolution:
getting the type right determines which evidence the investigate node gathers.
"""

from __future__ import annotations

from ledgerpilot.agent.state import AgentState


async def triage(state: AgentState) -> AgentState:
    """TODO(phase-5): classify break type + materiality, set triage_rationale."""
    raise NotImplementedError
