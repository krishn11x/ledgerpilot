from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from ledgerpilot.api.main import create_app
from ledgerpilot.domain.enums import MatchMethod, MatchStatus
from ledgerpilot.domain.models import JournalEntry, JournalLine, Match, MatchLeg
from ledgerpilot.store.db import create_all, session_scope
from ledgerpilot.store.repositories import JournalRepository, MatchRepository


@pytest.fixture(autouse=True)
def setup_db() -> None:
    create_all()


# ---------------------------------------------------------------------------
# RUNS Router Tests
# ---------------------------------------------------------------------------


def test_start_and_get_run(client: object) -> None:
    resp = client.post("/runs", json={"scenario": "baseline"})
    assert resp.status_code == 202
    data = resp.json()
    assert "run_id" in data
    assert "counts" in data

    run_id = data["run_id"]
    get_resp = client.get(f"/runs/{run_id}")
    assert get_resp.status_code == 200
    run_data = get_resp.json()
    assert run_data["run_id"] == run_id


def test_start_run_invalid_scenario_404(client: object) -> None:
    resp = client.post("/runs", json={"scenario": "unknown_scen"})
    assert resp.status_code == 404


def test_get_run_not_found_404(client: object) -> None:
    resp = client.get("/runs/RUN-nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# SCENARIOS Router Tests
# ---------------------------------------------------------------------------


def test_list_scenarios(client: object) -> None:
    resp = client.get("/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 1


def test_generate_scenario(client: object) -> None:
    resp = client.post("/scenarios/generate", json={"scenario": "baseline", "order_count": 10})
    assert resp.status_code == 202
    data = resp.json()
    assert "paths" in data
    assert "ground_truth" in data


def test_generate_scenario_invalid_404(client: object) -> None:
    resp = client.post("/scenarios/generate", json={"scenario": "invalid_scenario"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# MATCHES Router Tests
# ---------------------------------------------------------------------------


def test_list_matches(client: object) -> None:
    resp = client.get("/matches")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


def test_get_match(client: object) -> None:
    leg1 = MatchLeg(record_type="order", record_id="ord_1", amount_minor=1000)
    leg2 = MatchLeg(record_type="gateway_txn", record_id="gtw_1", amount_minor=1000)
    match = Match(
        match_id="MCH-test-1",
        method=MatchMethod.EXACT_REFERENCE,
        status=MatchStatus.CONFIRMED,
        confidence=1.0,
        legs=[leg1, leg2],
        created_at=datetime.now(UTC),
    )
    with session_scope() as session:
        MatchRepository(session).upsert(match)

    resp = client.get("/matches/MCH-test-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["match_id"] == "MCH-test-1"
    assert data["confidence"] == 1.0


def test_get_match_not_found_404(client: object) -> None:
    resp = client.get("/matches/MCH-nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# METRICS Router Tests
# ---------------------------------------------------------------------------


def test_get_metrics(client: object) -> None:
    resp = client.get("/metrics?scenario=baseline")
    assert resp.status_code == 200
    data = resp.json()
    assert "auto_match_rate" in data


def test_get_metrics_invalid_scenario_404(client: object) -> None:
    resp = client.get("/metrics?scenario=invalid_scen")
    assert resp.status_code == 404


def test_upload_requires_auth(client: object) -> None:
    with TestClient(create_app()) as unauthenticated:
        response = unauthenticated.post(
            "/upload",
            files={
                "orders": ("orders.csv", b"order_id,customer_id,gross_minor,currency,placed_at,status\nA1,C1,1000,INR,2024-01-01T00:00:00Z,paid\n"),
                "gateway_txns": ("gateway_txns.csv", b"txn_id,order_ref,gross_minor,fee_minor,tax_minor,net_minor,currency,status,payout_id,captured_at\nG1,A1,1000,0,0,1000,INR,paid,,2024-01-01T00:00:00Z\n"),
                "payouts": ("payouts.csv", b"payout_id,expected_net_minor,txn_count,currency,settled_on,utr\nP1,1000,1,INR,2024-01-01,UTR-1\n"),
                "bank_txns": ("bank_txns.csv", b"bank_txn_id,value_date,amount,direction,currency,narration,utr\nB1,2024-01-01,1000,credit,INR,Gateway settlement,UTR-1\n"),
            },
        )
        assert response.status_code == 401


def test_upload_accepts_real_data_and_returns_run(client: object) -> None:
    files = {
        "orders": ("orders.csv", open("data/synthetic/smoke/orders.csv", "rb")),
        "gateway_txns": ("gateway_txns.csv", open("data/synthetic/smoke/gateway_txns.csv", "rb")),
        "payouts": ("payouts.csv", open("data/synthetic/smoke/payouts.csv", "rb")),
        "bank_txns": ("bank_txns.csv", open("data/synthetic/smoke/bank_txns.csv", "rb")),
    }
    try:
        resp = client.post("/upload", files=files)
    finally:
        for file in files.values():
            file[1].close()

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["run_id"]
    assert data["status"] in {"completed", "running"}
    assert data["counts"]["breaks"] >= 0


def test_upload_rejects_invalid_extension(client: object) -> None:
    resp = client.post(
        "/upload",
        files={
            "orders": ("orders.txt", b"abc"),
            "gateway_txns": ("gateway_txns.csv", b"txn_id,order_ref,gross_minor,fee_minor,tax_minor,net_minor,currency,status,payout_id,captured_at\nG1,A1,1000,0,0,1000,INR,paid,,2024-01-01T00:00:00Z\n"),
            "payouts": ("payouts.csv", b"payout_id,expected_net_minor,txn_count,currency,settled_on,utr\nP1,1000,1,INR,2024-01-01,UTR-1\n"),
            "bank_txns": ("bank_txns.csv", b"bank_txn_id,value_date,amount,direction,currency,narration,utr\nB1,2024-01-01,1000,credit,INR,Gateway settlement,UTR-1\n"),
        },
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert "CSV or XLSX" in payload["error"]["message"]
    assert "CSV or XLSX" in str(payload["error"]["detail"] or "")


def test_dashboard_metrics(client: object) -> None:
    resp = client.get("/metrics/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "auto_match_rate" in data
    assert "value_unreconciled_minor" in data


# ---------------------------------------------------------------------------
# AUDIT Router Tests
# ---------------------------------------------------------------------------


def test_list_audit_events(client: object) -> None:
    resp = client.get("/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


def test_verify_audit_chain(client: object) -> None:
    resp = client.get("/audit/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert "intact" in data
    assert data["intact"] is True


# ---------------------------------------------------------------------------
# LEDGER Router Tests
# ---------------------------------------------------------------------------


def test_list_ledger_entries(client: object) -> None:
    resp = client.get("/ledger/entries")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


def test_approve_ledger_entry(client: object) -> None:
    entry = JournalEntry(
        entry_id="JRN-test-1",
        break_id="brk_1",
        lines=[
            JournalLine(account_code="1000", debit_minor=100, currency="USD"),
            JournalLine(account_code="2000", credit_minor=100, currency="USD"),
        ],
        status="proposed",
        posting_date=datetime.now(UTC).date(),
        rationale="Test journal entry",
        proposed_by="test",
    )
    with session_scope() as session:
        JournalRepository(session).propose(entry)

    resp = client.post("/ledger/entries/JRN-test-1/approve")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["approved_by"] == "api"


def test_approve_ledger_entry_not_found_404(client: object) -> None:
    resp = client.post("/ledger/entries/JRN-nonexistent/approve")
    assert resp.status_code == 404


def test_clearing_proof(client: object) -> None:
    resp = client.get("/ledger/clearing-proof")
    assert resp.status_code == 200
    data = resp.json()
    assert "proves_out" in data
    assert "variance_minor" in data
