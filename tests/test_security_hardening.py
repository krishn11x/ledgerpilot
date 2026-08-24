from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from ledgerpilot.api.main import create_app
from ledgerpilot.config import Settings


def test_feature_routes_require_bearer_auth() -> None:
    with TestClient(create_app()) as unauthenticated:
        assert unauthenticated.get("/metrics").status_code == 401
        assert unauthenticated.get("/breaks").status_code == 401
        assert unauthenticated.post("/runs", json={"scenario": "smoke"}).status_code == 401


def test_configured_bearer_auth_allows_feature_routes(client: Any) -> None:
    assert client.get("/metrics?scenario=clean").status_code == 200
    assert client.get("/breaks").status_code == 200


def test_runs_are_isolated(client: Any) -> None:
    first = client.post("/runs", json={"scenario": "clean"}).json()
    second = client.post("/runs", json={"scenario": "clean"}).json()
    assert first["run_id"] != second["run_id"]
    assert first["scenario"] == second["scenario"] == "clean"


def test_investigation_cannot_be_repeated(client: Any) -> None:
    client.post("/runs", json={"scenario": "smoke"})
    item = client.get("/breaks?status=open&limit=1").json()["items"][0]
    break_id = item["break_id"]
    assert client.post(f"/breaks/{break_id}/investigate").status_code == 202
    assert client.get(f"/breaks/{break_id}").json()["break"]["status"] == "pending_approval"
    assert client.post(f"/breaks/{break_id}/investigate").status_code == 409


def test_audit_uses_authenticated_actor_not_assignee(client: Any) -> None:
    client.post("/runs", json={"scenario": "smoke"})
    item = client.get("/breaks?status=open&limit=1").json()["items"][0]
    response = client.post(
        f"/breaks/{item['break_id']}/decision",
        json={"action": "escalate", "assignee": "untrusted-client-value"},
    )
    assert response.status_code == 200
    from ledgerpilot.audit.events import query

    events, _ = query(subject_id=item["break_id"], limit=10)
    assert events[-1].actor_id == "demo@ledgerpilot.local"
    assert response.json()["assignee"] == "untrusted-client-value"


def test_production_rejects_development_token() -> None:
    with pytest.raises(ValueError, match="LP_API_AUTH_TOKEN"):
        Settings(env="production", api_auth_token="local-demo-token")