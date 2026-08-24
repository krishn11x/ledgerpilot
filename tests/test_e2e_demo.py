from __future__ import annotations

from typing import Any


def test_smoke_demo_reaches_decision_audit_and_evaluation(client: Any) -> None:
    run_response = client.post("/runs", json={"scenario": "smoke"})
    assert run_response.status_code == 202
    run = run_response.json()
    assert run["status"] == "completed"
    assert run["counts"]["matches"] > 0
    assert run["counts"]["breaks"] > 0

    run_id = run["run_id"]
    assert client.get(f"/runs/{run_id}").status_code == 200

    queue = client.get("/breaks?status=open&limit=10")
    assert queue.status_code == 200
    item = queue.json()["items"][0]
    break_id = item["break_id"]

    investigation = client.post(f"/breaks/{break_id}/investigate")
    assert investigation.status_code == 202
    assert investigation.json()["decision"] in {"auto_resolve", "escalate"}

    decision = client.post(
        f"/breaks/{break_id}/decision",
        json={"action": "escalate", "note": "Deterministic demo review"},
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "escalated"

    assert client.get("/audit").json()["total"] > 0
    metrics = client.get("/metrics?scenario=clean")
    assert metrics.status_code == 200
    assert metrics.json()["auto_match_rate"] == 1.0
    assert client.get(f"/breaks/{break_id}").status_code == 200
