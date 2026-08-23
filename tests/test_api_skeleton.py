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


def test_unimplemented_endpoints_return_501(client: Any) -> None:
    """Scaffolded endpoints must say so, not return a misleading empty success."""
    for path in ("/breaks", "/matches/abc", "/audit", "/metrics", "/ledger/entries"):
        r = client.get(path)
        assert r.status_code == 501, f"{path} returned {r.status_code}"
        assert r.json()["error"]["code"] == "not_implemented"
