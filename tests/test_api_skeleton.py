"""API skeleton tests.

Asserts the contract the frontend is being built against: health works, the
scenario catalogue is real, unbuilt endpoints answer 501 rather than pretending
to succeed, and OpenAPI is emitted so the TypeScript client can be generated.
"""

from __future__ import annotations

from typing import Any


def test_root(client: Any) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "ledgerpilot"


def test_health(client: Any) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ok", "degraded"}
    assert "autonomy_level" in body
    assert "agent_available" in body


def test_openapi_available(client: Any) -> None:
    """The generated TS client depends on this staying valid."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "LedgerPilot API"
    assert "/health" in spec["paths"]
    assert "/breaks" in spec["paths"]


def test_scenarios_listing_is_implemented(client: Any) -> None:
    r = client.get("/scenarios")
    assert r.status_code == 200
    names = {item["name"] for item in r.json()["items"]}
    assert "baseline" in names


def test_feature_endpoints_are_implemented(client: Any) -> None:
    """Core API surfaces respond with real payloads, not scaffold errors."""
    assert client.get("/breaks").status_code == 200
    assert client.get("/matches/abc").status_code == 404
    assert client.get("/audit").status_code == 200
    assert client.get("/metrics").status_code == 200
    assert client.get("/ledger/entries").status_code == 200
