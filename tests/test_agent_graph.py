from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import MemorySaver

from ledgerpilot.agent.graph import build_graph
from ledgerpilot.agent.state import AgentState
from ledgerpilot.domain.enums import BreakType


@pytest.mark.asyncio
async def test_build_graph_without_checkpointer():
    graph = build_graph()
    assert graph is not None


@pytest.mark.asyncio
async def test_build_graph_with_checkpointer():
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    assert graph is not None


@pytest.mark.asyncio
async def test_graph_execution_auto_resolve_path():
    graph = build_graph()
    state: AgentState = {
        "break_id": "test_brk_1",
        "run_id": "run_1",
        "break_context": {
            "break_id": "test_brk_1",
            "break_type": BreakType.SHORT_PAYMENT,
            "amount_at_risk_minor": 100,
            "narration": "Short payment testing",
            "subject_ids": ["rec_1"],
        },
        "steps": [],
        "tokens_used": 0,
        "steps_used": 0,
        "retry_count": 0,
    }

    res = await graph.ainvoke(state)

    assert res["classified_type"] == "short_payment"
    assert res["steps_used"] >= 1
    assert "proposal" in res
    assert res["decision"] in {"auto_resolve", "escalate"}


@pytest.mark.asyncio
async def test_graph_execution_investigation_budget_escalate():
    graph = build_graph()
    state: AgentState = {
        "break_id": "test_brk_budget",
        "run_id": "run_budget",
        "break_context": {
            "break_id": "test_brk_budget",
            "break_type": BreakType.SHORT_PAYMENT,
            "amount_at_risk_minor": 100,
            "narration": "Short payment budget test",
        },
        "steps": [],
        "tokens_used": 0,
        "steps_used": 999,  # exceeding max steps
        "retry_count": 0,
    }

    res = await graph.ainvoke(state)

    assert res["decision"] == "escalate"
    assert res["decision_reason"] == "human review required"


@pytest.mark.asyncio
async def test_graph_execution_verification_retry_limit():
    graph = build_graph()
    state: AgentState = {
        "break_id": "test_brk_retry",
        "run_id": "run_retry",
        "break_context": {
            "break_id": "test_brk_retry",
            "break_type": BreakType.SHORT_PAYMENT,
            "amount_at_risk_minor": 100,
            "narration": "Short payment retry test",
            "subject_ids": [],
        },
        "steps": [],
        "tokens_used": 0,
        "steps_used": 0,
        "retry_count": 2,  # retry limit reached
    }

    res = await graph.ainvoke(state)

    assert res["decision"] == "escalate"
