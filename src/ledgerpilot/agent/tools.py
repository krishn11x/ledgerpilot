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

from ledgerpilot.config import settings
from ledgerpilot.domain.policy import FeeSchedule
from ledgerpilot.ingest.normalize import extract_references, normalize_narration
from ledgerpilot.recon.scoring import combined_score, score_amount, score_date, score_narration
from ledgerpilot.store.db import session_scope
from ledgerpilot.store.repositories import (
    BankRepository,
    GatewayRepository,
    OrderRepository,
)

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
    with session_scope() as session:
        repo = OrderRepository(session)
        items = repo.all()
        result = []
        for item in items:
            if amount_minor is not None and item.gross_minor != amount_minor:
                continue
            if customer_id is not None and item.customer_id != customer_id:
                continue
            if date_from is not None and item.placed_at.date().isoformat() < date_from:
                continue
            if date_to is not None and item.placed_at.date().isoformat() > date_to:
                continue
            result.append(item.model_dump())
        return result


def search_gateway_txns(
    *,
    order_ref: str | None = None,
    amount_minor: int | None = None,
    payout_id: str | None = None,
) -> list[dict[str, Any]]:
    """TODO(phase-5): find gateway transactions."""
    with session_scope() as session:
        repo = GatewayRepository(session)
        items = repo.all()
        result = []
        for item in items:
            if order_ref is not None and item.order_ref != order_ref:
                continue
            if amount_minor is not None and item.gross_minor != amount_minor:
                continue
            if payout_id is not None and item.payout_id != payout_id:
                continue
            result.append(item.model_dump())
        return result


def search_bank_txns(
    *,
    amount_minor: int | None = None,
    narration_contains: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """TODO(phase-5): find bank statement lines."""
    with session_scope() as session:
        repo = BankRepository(session)
        items = repo.all()
        result = []
        for item in items:
            if amount_minor is not None and item.amount_minor != amount_minor:
                continue
            if narration_contains is not None and narration_contains.lower() not in (
                item.narration.lower()
            ):
                continue
            if date_from is not None and item.value_date.isoformat() < date_from:
                continue
            if date_to is not None and item.value_date.isoformat() > date_to:
                continue
            result.append(item.model_dump())
        return result


# ---------------------------------------------------------------------------
# Reasoning-support tools
# ---------------------------------------------------------------------------


def fuzzy_candidates(record_type: str, record_id: str) -> list[dict[str, Any]]:
    """TODO(phase-5): the same candidates the engine's fuzzy pass considered.

    Reusing the engine's own generator guarantees the agent reasons over the
    exact evidence the rules saw -- no divergence between the two layers.
    """
    if record_type != "order":
        return []
    with session_scope() as session:
        orders = OrderRepository(session).all()
        gtxns = GatewayRepository(session).all()
        target = next((o for o in orders if o.order_id == record_id), None)
        if target is None:
            return []
        candidates: list[dict[str, Any]] = []
        for txn in gtxns:
            if txn.currency != target.currency:
                continue
            date_delta = abs((txn.captured_at.date() - target.placed_at.date()).days)
            features = {
                "amount": score_amount(target.gross_minor, txn.gross_minor),
                "date": score_date(date_delta, window_days=settings.date_window_days),
                "narration": score_narration(normalize_narration(txn.txn_id), target.order_id),
            }
            candidates.append(
                {
                    "candidate_id": txn.txn_id,
                    "features": features,
                    "score": combined_score(features),
                }
            )
        return candidates


def parse_narration(narration: str) -> dict[str, Any]:
    """TODO(phase-5): LLM-assisted entity extraction from bank narration.

    The one genuinely LLM-shaped subtask. Regex handles known formats in
    ``ingest.normalize``; this covers the long tail.
    """
    parsed = extract_references(narration)
    parsed["normalized"] = normalize_narration(narration)
    return parsed


def lookup_fee_schedule(gateway: str, method: str) -> dict[str, Any]:
    """TODO(phase-5): expected fee terms, so variance is computed not guessed."""
    schedule = FeeSchedule(
        bps=settings.gateway_fee_bps,
        flat_minor=settings.gateway_fee_flat_minor,
        tax_bps=settings.gateway_tax_bps,
    )
    return {
        "gateway": gateway,
        "method": method,
        "fee_bps": schedule.bps,
        "flat_minor": schedule.flat_minor,
        "tax_bps": schedule.tax_bps,
    }


def lookup_fx_rate(base: str, quote: str, as_of: str) -> dict[str, Any]:
    """TODO(phase-5): dated rate for FX variance analysis."""
    if base == quote:
        rate = 1
    elif base == "USD" and quote == settings.base_currency:
        rate = 83.25
    elif quote == "USD" and base == settings.base_currency:
        rate = 1 / 83.25
    else:
        rate = None
    return {"base": base, "quote": quote, "as_of": as_of, "rate": rate}


def check_arithmetic(expression: dict[str, Any]) -> dict[str, Any]:
    """TODO(phase-5): evaluate a structured money computation exactly.

    Integer minor units in, integer minor units out. The agent never performs
    arithmetic itself -- it calls this and cites the result.
    """
    op = expression.get("op")
    operands = expression.get("operands", [])
    if op == "add":
        value = sum(int(x) for x in operands)
    elif op == "sub" and len(operands) == 2:
        value = int(operands[0]) - int(operands[1])
    elif op == "mul" and len(operands) == 2:
        value = int(operands[0]) * int(operands[1])
    elif op == "div" and len(operands) == 2:
        value = int(int(operands[0]) / int(operands[1]))
    else:
        raise ValueError("unsupported arithmetic expression")
    return {"value_minor": value}


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
