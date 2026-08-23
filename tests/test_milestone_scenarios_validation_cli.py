"""Tests for scenarios materialization, validation, and CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ledgerpilot.cli import app
from ledgerpilot.ingest.validate import (
    ValidationReport,
    validate_bank_txns,
    validate_gateway_txns,
    validate_orders,
    validate_payouts,
)
from ledgerpilot.synth.scenarios import SCENARIOS, get_scenario, materialize

runner = CliRunner()


def test_get_scenario_valid_and_invalid() -> None:
    for name in SCENARIOS:
        scen = get_scenario(name)
        assert scen.name == name

    with pytest.raises(KeyError, match="Unknown scenario 'nonexistent'"):
        get_scenario("nonexistent")


def test_materialize_smoke(tmp_path: Path) -> None:
    out_dir = tmp_path / "smoke_out"
    paths = materialize("smoke", out_dir=out_dir)

    assert "orders" in paths
    assert "gateway_txns" in paths
    assert "payouts" in paths
    assert "bank_txns" in paths
    assert "manifest" in paths
    assert "ground_truth" in paths

    assert Path(paths["orders"]).exists()
    assert Path(paths["ground_truth"]).exists()


def test_validation_report_acceptance_rate() -> None:
    rep_empty = ValidationReport(source="orders", total_rows=0, accepted=0)
    assert rep_empty.acceptance_rate == 1.0

    rep = ValidationReport(source="orders", total_rows=10, accepted=8)
    assert rep.acceptance_rate == 0.8


def test_validate_orders_valid_and_invalid() -> None:
    valid_row = {
        "order_id": "ORD-0000001",
        "customer_id": "CUST-000001",
        "gross_minor": "1000",
        "currency": "INR",
        "placed_at": "2026-07-01T10:00:00+00:00",
        "status": "paid",
    }
    invalid_row = {
        "order_id": "ORD-0000002",
        "customer_id": "CUST-000001",
        "gross_minor": "-500",
        "currency": "INR",
        "placed_at": "2026-07-01T10:00:00+00:00",
        "status": "paid",
    }

    accepted, report = validate_orders([valid_row, invalid_row])
    assert len(accepted) == 1
    assert accepted[0]["order_id"] == "ORD-0000001"
    assert report.total_rows == 2
    assert report.accepted == 1
    assert len(report.quarantined) == 1
    assert report.quarantined[0].row_number == 2


def test_validate_gateway_txns_arithmetic() -> None:
    valid_row = {
        "txn_id": "PAY-0000001",
        "order_ref": "ORD-0000001",
        "gross_minor": "1000",
        "fee_minor": "20",
        "tax_minor": "3",
        "net_minor": "977",
        "currency": "INR",
        "status": "captured",
        "payout_id": "POUT-00001",
        "captured_at": "2026-07-01T10:05:00+00:00",
    }
    invalid_row = {
        "txn_id": "PAY-0000002",
        "order_ref": "ORD-0000002",
        "gross_minor": "1000",
        "fee_minor": "20",
        "tax_minor": "3",
        "net_minor": "999",
        "currency": "INR",
        "status": "captured",
        "payout_id": "POUT-00001",
        "captured_at": "2026-07-01T10:05:00+00:00",
    }

    accepted, report = validate_gateway_txns([valid_row, invalid_row])
    assert len(accepted) == 1
    assert len(report.quarantined) == 1
    assert "arithmetic mismatch" in report.quarantined[0].reason


def test_validate_payouts_and_bank() -> None:
    valid_payout = {
        "payout_id": "POUT-00001",
        "expected_net_minor": "5000",
        "txn_count": "5",
        "currency": "INR",
        "settled_on": "2026-07-03",
        "utr": "123456789012",
    }
    accepted_p, rep_p = validate_payouts([valid_payout])
    assert len(accepted_p) == 1
    assert rep_p.accepted == 1

    valid_bank = {
        "bank_txn_id": "BNK-0000001",
        "value_date": "2026-07-03",
        "amount": "50.00",
        "direction": "credit",
        "currency": "INR",
        "narration": "NEFT-RAZORPAY-UTR123456789012-STLMNT/JUL",
        "utr": "",
    }
    accepted_b, rep_b = validate_bank_txns([valid_bank])
    assert len(accepted_b) == 1
    assert rep_b.accepted == 1


def test_cli_db_init() -> None:
    result = runner.invoke(app, ["db", "init"])
    assert result.exit_code == 0
    assert "Schema created" in result.output


def test_cli_generate_and_ingest() -> None:
    gen_result = runner.invoke(app, ["generate", "--scenario", "smoke"])
    assert gen_result.exit_code == 0
    assert "Materialised scenario 'smoke' successfully" in gen_result.output

    ingest_result = runner.invoke(app, ["ingest", "--scenario", "smoke"])
    assert ingest_result.exit_code == 0
    assert "Ingest run" in ingest_result.output
    assert "completed successfully" in ingest_result.output
