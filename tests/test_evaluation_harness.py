from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerpilot.domain.enums import BreakType, ExpectedOutcome, ResolutionCategory
from ledgerpilot.evaluation.harness import (
    check_thresholds,
    compare_reports,
    report_to_dict,
    run_evaluation,
    save_report,
)
from ledgerpilot.evaluation.metrics import (
    ConfusionCounts,
    EvalReport,
    compute_confusion,
    false_positive_match_rate,
)
from ledgerpilot.synth.breaks import BreakMix, GroundTruthLabel, write_ground_truth
from ledgerpilot.synth.generator import SyntheticGenerator


def test_compute_confusion_matrix() -> None:
    actual = [("rec_1", BreakType.SHORT_PAYMENT), ("rec_2", BreakType.FEE_VARIANCE)]
    predicted = [("rec_1", BreakType.SHORT_PAYMENT), ("rec_3", BreakType.CHARGEBACK)]

    counts = compute_confusion(predicted, actual)
    assert counts[BreakType.SHORT_PAYMENT].true_positive == 1
    assert counts[BreakType.FEE_VARIANCE].false_negative == 1
    assert counts[BreakType.CHARGEBACK].false_positive == 1

    sp = counts[BreakType.SHORT_PAYMENT]
    assert sp.precision == 1.0
    assert sp.recall == 1.0
    assert sp.f1 == 1.0


def test_false_positive_match_rate() -> None:
    committed = [("rec_1", "rec_2"), ("rec_3", "rec_4")]
    true_pairings = {("rec_1", "rec_2")}

    fp_rate = false_positive_match_rate(committed, true_pairings)
    assert fp_rate == 0.5


def test_run_evaluation_baseline() -> None:
    report = run_evaluation("baseline", with_agent=False)
    assert report.scenario == "baseline"
    assert report.total_records > 0
    assert 0.0 <= report.auto_match_rate <= 1.0
    assert report.wall_clock_seconds >= 0.0


def test_check_thresholds_passing() -> None:
    report = EvalReport(
        scenario="test",
        seed=42,
        auto_match_rate=0.95,
        false_positive_match_rate=0.0,
        per_type={
            BreakType.SHORT_PAYMENT: ConfusionCounts(
                true_positive=10, false_positive=0, false_negative=0
            )
        },
    )
    passed, failures = check_thresholds(report)
    assert passed is True
    assert len(failures) == 0


def test_check_thresholds_failing() -> None:
    report = EvalReport(
        scenario="test",
        seed=42,
        auto_match_rate=0.50,  # below min 0.85
        false_positive_match_rate=0.05,  # above max 0.001
        per_type={
            BreakType.SHORT_PAYMENT: ConfusionCounts(
                true_positive=1, false_positive=10, false_negative=10
            )
        },
    )
    passed, failures = check_thresholds(report)
    assert passed is False
    assert len(failures) >= 2


def test_compare_reports() -> None:
    r1 = EvalReport(
        scenario="baseline",
        seed=1,
        auto_match_rate=0.85,
        false_positive_match_rate=0.001,
        value_unreconciled_minor=1000,
    )
    r2 = EvalReport(
        scenario="candidate",
        seed=2,
        auto_match_rate=0.90,
        false_positive_match_rate=0.000,
        value_unreconciled_minor=500,
    )
    diff = compare_reports(r1, r2)
    assert "# Evaluation diff: baseline -> candidate" in diff
    assert "auto_match_rate" in diff
    assert "| auto_match_rate | 0.8500 | 0.9000 | +0.0500 |" in diff


def test_save_report(tmp_path: Path) -> None:
    report = EvalReport(
        scenario="baseline",
        seed=42,
        auto_match_rate=0.90,
        per_type={
            BreakType.SHORT_PAYMENT: ConfusionCounts(
                true_positive=5, false_positive=0, false_negative=1
            )
        },
    )
    json_path = tmp_path / "report.json"
    save_report(report, json_path)

    assert json_path.exists()
    md_path = json_path.with_suffix(".md")
    assert md_path.exists()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["scenario"] == "baseline"
    assert "per_type" in data
    assert "short_payment" in data["per_type"]

    md_content = md_path.read_text(encoding="utf-8")
    assert "# Evaluation report: baseline" in md_content


def test_report_to_dict_serializable() -> None:
    report = EvalReport(
        scenario="test",
        seed=1,
        per_type={BreakType.FEE_VARIANCE: ConfusionCounts(true_positive=2, false_positive=1)},
    )
    d = report_to_dict(report)
    json_str = json.dumps(d)
    assert "fee_variance" in json_str
    assert "macro_precision" in d


def test_break_mix_total_rate_excludes_non_break_mutations() -> None:
    mix = BreakMix(timing_straddle=1.0, narration_noise=1.0)
    assert mix.total_break_rate() == pytest.approx(0.198)


def test_write_ground_truth_round_trips(tmp_path: Path) -> None:
    label = GroundTruthLabel(
        label_id="GT-1",
        scenario="smoke",
        seed=1,
        break_type=BreakType.SHORT_PAYMENT,
        expected_outcome=ExpectedOutcome.UNMATCHED,
        resolution_category=ResolutionCategory.INVESTIGATE,
        affected_ids=["PAY-1"],
        amount_at_risk_minor=100,
        currency="INR",
        injector="test",
    )
    path = tmp_path / "ground_truth.json"
    write_ground_truth([label], str(path))
    assert GroundTruthLabel.from_dict(json.loads(path.read_text())[0]) == label


def test_missing_injectors_emit_deterministic_labels() -> None:
    dataset = SyntheticGenerator(seed=11, period_days=7).generate(order_count=100)
    mix = BreakMix(
        missing_in_gateway=0.0,
        unsettled=0.0,
        duplicate_payment=0.0,
        payout_mismatch=0.0,
        fee_variance=1.0,
        narration_noise=1.0,
    )
    from ledgerpilot.synth.breaks import BreakInjector

    _, labels = BreakInjector(seed=11).inject(dataset, mix)
    assert any(label.break_type is BreakType.FEE_VARIANCE for label in labels)
    assert any(label.break_type is None for label in labels)
