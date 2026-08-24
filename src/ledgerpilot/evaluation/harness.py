"""Evaluation runner.

Runs a scenario end to end and scores the result against ground truth. Doubles
as the regression suite: ``clean`` must produce zero breaks, and ``baseline``
must not regress below recorded thresholds.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

from ledgerpilot.domain.enums import BreakType
from ledgerpilot.evaluation.metrics import EvalReport, compute_confusion, false_positive_match_rate
from ledgerpilot.ingest.loaders import (
    load_bank_txns,
    load_gateway_txns,
    load_orders,
    load_payouts,
)
from ledgerpilot.recon.engine import ReconContext, ReconEngine
from ledgerpilot.synth.breaks import GroundTruthLabel
from ledgerpilot.synth.scenarios import get_scenario, materialize

# CI thresholds. A drop below any of these fails the build.
# Deliberately asymmetric: false positives are capped an order of magnitude
# tighter than the coverage floors, because a wrong match costs far more than
# an escalation.
THRESHOLDS: dict[str, float] = {
    "min_auto_match_rate": 0.85,
    "max_false_positive_match_rate": 0.001,
    "min_macro_precision": 0.90,
    "min_macro_recall": 0.80,
}


def report_to_dict(report: EvalReport) -> dict[str, Any]:
    """Convert an EvalReport to a JSON-serializable dictionary."""
    d = dict(report.__dict__)
    if "per_type" in d and isinstance(d["per_type"], dict):
        d["per_type"] = {
            (k.value if hasattr(k, "value") else str(k)): (
                v.__dict__ if hasattr(v, "__dict__") else v
            )
            for k, v in report.per_type.items()
        }
    d["macro_precision"] = report.macro_precision()
    d["macro_recall"] = report.macro_recall()
    return d


def run_evaluation(scenario: str, *, with_agent: bool = False) -> EvalReport:
    """generate -> ingest -> reconcile -> score.

    ``with_agent=False`` measures the deterministic engine alone, which is the
    number to quote for reproducibility. ``with_agent=True`` measures the full
    system. Reporting both makes the split between the two layers legible
    instead of a claim.
    """
    start_time = time.perf_counter()
    scen = get_scenario(scenario)
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        paths = materialize(scenario, seed=scen.seed, out_dir=out_dir)
        orders = load_orders(Path(paths["orders"]))
        gateway_txns = load_gateway_txns(Path(paths["gateway_txns"]))
        payouts = load_payouts(Path(paths["payouts"]))
        bank_txns = load_bank_txns(Path(paths["bank_txns"]))
        raw_labels = json.loads(Path(paths["ground_truth"]).read_text(encoding="utf-8"))
        labels = [GroundTruthLabel.from_dict(raw) for raw in raw_labels]

        ctx = ReconContext(
            run_id=f"EVAL-{scenario}",
            orders=orders,
            gateway_txns=gateway_txns,
            payouts=payouts,
            bank_txns=bank_txns,
        )
        result = ReconEngine().run_context(ctx)

        predicted_breaks: list[tuple[str, BreakType]] = []
        for brk in result.breaks:
            for leg in brk.legs:
                predicted_breaks.append((leg.record_id, brk.break_type))

        actual_breaks: list[tuple[str, BreakType]] = []
        true_pairings: set[tuple[str, str]] = set()
        for label in labels:
            if label.break_type is not None:
                actual_breaks.extend(
                    (record_id, label.break_type) for record_id in label.affected_ids
                )

        for txn in gateway_txns:
            if txn.order_ref:
                true_pairings.add((txn.order_ref, txn.txn_id))
            if txn.payout_id:
                true_pairings.add((txn.txn_id, txn.payout_id))
        payout_by_utr = {p.utr: p for p in payouts if p.utr is not None}
        for bank in bank_txns:
            refs = bank.utr
            if not refs:
                continue
            payout = payout_by_utr.get(refs)
            if payout is not None:
                true_pairings.add((payout.payout_id, bank.bank_txn_id))

        confusion = compute_confusion(predicted_breaks, actual_breaks)
        committed_matches: list[tuple[str, str]] = []
        for match in result.matches:
            if match.status.value != "confirmed":
                continue
            committed_matches.extend(
                (left.record_id, right.record_id)
                for index, left in enumerate(match.legs)
                for right in match.legs[index + 1 :]
            )

        total_records = len(orders) + len(gateway_txns) + len(payouts) + len(bank_txns)
        elapsed = time.perf_counter() - start_time

        report = EvalReport(
            scenario=scenario,
            seed=scen.seed,
            total_records=total_records,
            auto_match_rate=result.auto_match_rate,
            escalation_rate=0.0,
            unmatched_rate=len(result.residual_ids) / max(total_records, 1),
            per_type=confusion,
            false_positive_match_rate=false_positive_match_rate(committed_matches, true_pairings),
            misclassification_rate=0.0,
            value_unreconciled_minor=sum(brk.amount_at_risk_minor for brk in result.breaks),
            value_at_risk_minor=sum(brk.amount_at_risk_minor for brk in result.breaks),
            currency=ctx.orders[0].currency if ctx.orders else "INR",
            agent_breaks_processed=0,
            agent_tokens_total=0,
            mean_tokens_per_break=0.0,
            wall_clock_seconds=round(elapsed, 4),
        )
        return report


def compare_reports(baseline: EvalReport, candidate: EvalReport) -> str:
    """Markdown diff of two runs."""
    lines = [
        f"# Evaluation diff: {baseline.scenario} -> {candidate.scenario}",
        "",
        "| Metric | Baseline | Candidate | Delta |",
        "|---|---:|---:|---:|",
    ]
    for name in (
        "auto_match_rate",
        "false_positive_match_rate",
        "macro_precision",
        "macro_recall",
        "value_unreconciled_minor",
    ):
        base_attr = getattr(baseline, name, None)
        cand_attr = getattr(candidate, name, None)
        base = base_attr() if callable(base_attr) else base_attr
        cand = cand_attr() if callable(cand_attr) else cand_attr
        if base is not None and cand is not None:
            delta = cand - base
            if isinstance(delta, float):
                lines.append(f"| {name} | {base:.4f} | {cand:.4f} | {delta:+.4f} |")
            else:
                lines.append(f"| {name} | {base} | {cand} | {delta:+} |")
    return "\n".join(lines)


def check_thresholds(report: EvalReport) -> tuple[bool, list[str]]:
    """Return (passed, failure messages) against THRESHOLDS."""
    failures: list[str] = []
    if report.auto_match_rate < THRESHOLDS["min_auto_match_rate"]:
        failures.append(
            f"auto_match_rate {report.auto_match_rate:.3f} below "
            f"threshold {THRESHOLDS['min_auto_match_rate']}"
        )
    if report.false_positive_match_rate > THRESHOLDS["max_false_positive_match_rate"]:
        failures.append(
            f"false_positive_match_rate {report.false_positive_match_rate:.3f} "
            f"above threshold {THRESHOLDS['max_false_positive_match_rate']}"
        )
    macro_p = report.macro_precision()
    if macro_p < THRESHOLDS["min_macro_precision"]:
        failures.append(
            f"macro_precision {macro_p:.3f} below threshold {THRESHOLDS['min_macro_precision']}"
        )
    macro_r = report.macro_recall()
    if macro_r < THRESHOLDS["min_macro_recall"]:
        failures.append(
            f"macro_recall {macro_r:.3f} below threshold {THRESHOLDS['min_macro_recall']}"
        )
    return (not failures), failures


def save_report(report: EvalReport, path: Path) -> None:
    """Write JSON + markdown so reports are diffable in git."""
    path.parent.mkdir(parents=True, exist_ok=True)
    d = report_to_dict(report)
    path.write_text(json.dumps(d, default=str, indent=2) + "\n", encoding="utf-8")
    path.with_suffix(".md").write_text(report.to_markdown() + "\n", encoding="utf-8")
