from datetime import UTC, datetime

from ledgerpilot.domain.enums import MatchMethod, MatchStatus, TxnDirection
from ledgerpilot.domain.models import BankTxn, GatewayTxn, Order, PayoutBatch
from ledgerpilot.recon.engine import ReconContext, ReconEngine
from ledgerpilot.recon.keys import amount_bucket, date_bucket, match_id_for
from ledgerpilot.recon.rules.aggregate import AggregatePayoutRule, SubsetSumRule
from ledgerpilot.recon.rules.exact import ExactReferenceRule
from ledgerpilot.recon.scoring import pick_best, score_amount, score_date


def test_keys_and_buckets() -> None:
    now = datetime.now(UTC).date()
    amt_key = amount_bucket(12500)
    assert amt_key == "AMT-1"

    dates = date_bucket(now, window_days=1)
    assert len(dates) == 3

    m_id1 = match_id_for([("order", "ORD-1"), ("gateway_txn", "GTX-1")])
    m_id2 = match_id_for([("gateway_txn", "GTX-1"), ("order", "ORD-1")])
    assert m_id1 == m_id2
    assert m_id1.startswith("MCH-")


def test_scoring_helpers() -> None:
    assert score_amount(1000, 1000) == 1.0
    assert score_amount(900, 1000) == 0.9

    assert score_date(0, window_days=3) == 1.0
    assert score_date(1, window_days=3) > 0.5
    assert score_date(4, window_days=3) == 0.0

    best = pick_best([], min_score=0.8, min_margin=0.05)
    assert best is None


def test_exact_reference_rule() -> None:
    now = datetime.now(UTC)
    order = Order(
        order_id="ORD-100",
        customer_id="CUST-1",
        gross_minor=10000,
        currency="INR",
        placed_at=now,
        status="completed",
    )
    gtxn = GatewayTxn(
        txn_id="GTX-100",
        order_ref="ORD-100",
        gross_minor=10000,
        fee_minor=200,
        tax_minor=36,
        net_minor=9764,
        currency="INR",
        status="captured",
        payout_id="POUT-0001",
        captured_at=now,
    )

    ctx = ReconContext(run_id="run-1", orders=[order], gateway_txns=[gtxn])
    rule = ExactReferenceRule()
    res = rule.apply(ctx, unmatched={"ORD-100", "GTX-100"})

    assert len(res.matches) == 1
    assert res.matches[0].status == MatchStatus.CONFIRMED
    assert res.matches[0].method == MatchMethod.EXACT_REFERENCE
    assert res.consumed_ids == {"ORD-100", "GTX-100"}


def test_aggregate_payout_rule() -> None:
    now_date = datetime.now(UTC).date()
    payout = PayoutBatch(
        payout_id="POUT-0099",
        expected_net_minor=9764,
        txn_count=1,
        currency="INR",
        settled_on=now_date,
        utr="UTR123456",
    )
    bank = BankTxn(
        bank_txn_id="BNK-99",
        value_date=now_date,
        amount_minor=9764,
        direction=TxnDirection.CREDIT,
        currency="INR",
        narration="CMS PAYOUT POUT-0099 UTR123456",
        utr="UTR123456",
    )

    ctx = ReconContext(run_id="run-2", payouts=[payout], bank_txns=[bank])
    rule = AggregatePayoutRule()
    res = rule.apply(ctx, unmatched={"POUT-0099", "BNK-99"})

    assert len(res.matches) == 1
    assert res.matches[0].status == MatchStatus.CONFIRMED
    assert res.consumed_ids == {"POUT-0099", "BNK-99"}


def test_subset_sum_rule() -> None:
    rule = SubsetSumRule()
    pool = [1000, 2500, 3000, 4500]
    indices = rule.find_subset(pool, target_minor=5500)
    assert indices is not None
    assert sum(pool[i] for i in indices) == 5500


def test_full_recon_cascade() -> None:
    now = datetime.now(UTC)
    now_date = now.date()

    order = Order(
        order_id="ORD-200",
        customer_id="CUST-2",
        gross_minor=50000,
        currency="INR",
        placed_at=now,
        status="completed",
    )
    gtxn = GatewayTxn(
        txn_id="GTX-200",
        order_ref="ORD-200",
        gross_minor=50000,
        fee_minor=1000,
        tax_minor=180,
        net_minor=48820,
        currency="INR",
        status="captured",
        payout_id="PO-200",
        captured_at=now,
    )
    payout = PayoutBatch(
        payout_id="PO-200",
        expected_net_minor=48820,
        txn_count=1,
        currency="INR",
        settled_on=now_date,
        utr="UTR999888",
    )
    bank = BankTxn(
        bank_txn_id="BNK-200",
        value_date=now_date,
        amount_minor=48820,
        direction=TxnDirection.CREDIT,
        currency="INR",
        narration="TRANSFER UTR999888 PO-200",
        utr="UTR999888",
    )

    ctx = ReconContext(
        run_id="run-full",
        orders=[order],
        gateway_txns=[gtxn],
        payouts=[payout],
        bank_txns=[bank],
    )

    engine = ReconEngine()
    result = engine.run_context(ctx)

    assert len(result.passes) == 5
    assert result.auto_match_rate == 1.0
    assert len(result.residual_ids) == 0
