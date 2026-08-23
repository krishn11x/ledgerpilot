"""Read-only tool surface for the agent. PLACEHOLDER -- signatures only.

Every tool here is a *query*. There is deliberately no write tool, no SQL
passthrough, and no shell access: the agent physically cannot mutate state, so
"what if the LLM does something destructive" is answered by construction rather
than by prompt instructions.

Note ``check_arithmetic``: the agent is given a calculator tool rather than
being asked to do mental math. Every number it reports traces back to a
deterministic computation.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Lookup tools
# ---------------------------------------------------------------------------


def search_orders(
    *,
    amount_minor: int | None = None,
    customer_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """TODO(phase-5): find orders matching the given filters."""
    raise NotImplementedError


def search_gateway_txns(
    *,
    order_ref: str | None = None,
    amount_minor: int | None = None,
    payout_id: str | None = None,
) -> list[dict[str, Any]]:
    """TODO(phase-5): find gateway transactions."""
    raise NotImplementedError


def search_bank_txns(
    *,
    amount_minor: int | None = None,
    narration_contains: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """TODO(phase-5): find bank statement lines."""
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Reasoning-support tools
# ---------------------------------------------------------------------------


def fuzzy_candidates(record_type: str, record_id: str) -> list[dict[str, Any]]:
    """TODO(phase-5): the same candidates the engine's fuzzy pass considered.

    Reusing the engine's own generator guarantees the agent reasons over the
    exact evidence the rules saw -- no divergence between the two layers.
    """
    raise NotImplementedError


def parse_narration(narration: str) -> dict[str, Any]:
    """TODO(phase-5): LLM-assisted entity extraction from bank narration.

    The one genuinely LLM-shaped subtask. Regex handles known formats in
    ``ingest.normalize``; this covers the long tail.
    """
    raise NotImplementedError


def lookup_fee_schedule(gateway: str, method: str) -> dict[str, Any]:
    """TODO(phase-5): expected fee terms, so variance is computed not guessed."""
    raise NotImplementedError


def lookup_fx_rate(base: str, quote: str, as_of: str) -> dict[str, Any]:
    """TODO(phase-5): dated rate for FX variance analysis."""
    raise NotImplementedError


def check_arithmetic(expression: dict[str, Any]) -> dict[str, Any]:
    """TODO(phase-5): evaluate a structured money computation exactly.

    Integer minor units in, integer minor units out. The agent never performs
    arithmetic itself -- it calls this and cites the result.
    """
    raise NotImplementedError


# Registry consumed by ``graph.build_graph`` when binding tools to the model.
READ_ONLY_TOOLS: tuple[str, ...] = (
    "search_orders",
    "search_gateway_txns",
    "search_bank_txns",
    "fuzzy_candidates",
    "parse_narration",
    "lookup_fee_schedule",
    "lookup_fx_rate",
    "check_arithmetic",
)
