"""Evaluation runner. PLACEHOLDER -- signatures only.

Runs a scenario end to end and scores the result against ground truth. Doubles
as the regression suite: ``clean`` must produce zero breaks, and ``baseline``
must not regress below recorded thresholds.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ledgerpilot.domain.enums import BreakType
from ledgerpilot.evaluation.metrics import EvalReport, compute_confusion, false_positive_match_rate
from ledgerpilot.ingest.loaders import (
    load_bank_txns,
    load_gateway_txns,
    load_orders,
    load_payouts,
)
from ledgerpilot.recon.engine import ReconContext, ReconEngine
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


def run_evaluation(scenario: str, *, with_agent: bool = False) -> EvalReport:
    """TODO(phase-3): generate -> ingest -> reconcile -> score.

    ``with_agent=False`` measures the deterministic engine alone, which is the
    number to quote for reproducibility. ``with_agent=True`` measures the full
    system. Reporting both makes the split between the two layers legible
    instead of a claim.
    """
    scen = get_scenario(scenario)
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        paths = materialize(scenario, seed=scen.seed, out_dir=out_dir)
        orders = load_orders(Path(paths["orders"]))
        gateway_txns = load_gateway_txns(Path(paths["gateway_txns"]))
        payouts = load_payouts(Path(paths["payouts"]))
        bank_txns = load_bank_txns(Path(paths["bank_txns"]))
        labels = json.loads(Path(paths["ground_truth"]).read_text(encoding="utf-8"))

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
        for raw in labels:
            break_type = raw.get("break_type")
            if break_type is not None:
                bt = BreakType(break_type)
                for record_id in raw.get("affected_ids", []):
                    actual_breaks.append((record_id, bt))

        for txn in gateway_txns:
            if txn.order_ref:
                true_pairings.add(tuple(sorted((txn.order_ref, txn.txn_id))))
        payout_by_utr = {p.utr: p for p in payouts if p.utr is not None}
        for bank in bank_txns:
            refs = bank.utr
            if not refs:
                continue
            payout = payout_by_utr.get(refs)
            if payout is not None:
                true_pairings.add(tuple(sorted((payout.payout_id, bank.bank_txn_id))))

        confusion = compute_confusion(predicted_breaks, actual_breaks)
        committed_matches = []
        for match in result.matches:
            if len(match.legs) >= 2:
                committed_matches.append((match.legs[0].record_id, match.legs[1].record_id))

        report = EvalReport(
            scenario=scenario,
            seed=scen.seed,
            total_records=len(orders) + len(gateway_txns) + len(payouts) + len(bank_txns),
            auto_match_rate=1.0
            if not result.matches
            else len([m for m in result.matches if m.status.value == "confirmed"]) / max(
                len(orders) + len(gateway_txns) + len(payouts) + len(bank_txns), 1
            ),
            escalation_rate=0.0,
            unmatched_rate=len(result.residual_ids)
            / max(len(orders) + len(gateway_txns) + len(payouts) + len(bank_txns), 1),
            per_type=confusion,
            false_positive_match_rate=false_positive_match_rate(committed_matches, true_pairings),
            misclassification_rate=0.0,
            value_unreconciled_minor=sum(brk.amount_at_risk_minor for brk in result.breaks),
            value_at_risk_minor=sum(brk.amount_at_risk_minor for brk in result.breaks),
            currency=ctx.orders[0].currency if ctx.orders else "INR",
            agent_breaks_processed=0,
            agent_tokens_total=0,
            mean_tokens_per_break=0.0,
            wall_clock_seconds=0.0,
        )
        return report


def compare_reports(baseline: EvalReport, candidate: EvalReport) -> str:
    """TODO: markdown diff of two runs, for PR comments."""
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
        delta = cand - base
        lines.append(f"| {name} | {base} | {cand} | {delta:+} |")
    return "\n".join(lines)


def check_thresholds(report: EvalReport) -> tuple[bool, list[str]]:
    """TODO: return (passed, failure messages) against THRESHOLDS."""
    failures: list[str] = []
    if report.auto_match_rate < THRESHOLDS["min_auto_match_rate"]:
        failures.append("auto_match_rate below threshold")
    if report.false_positive_match_rate > THRESHOLDS["max_false_positive_match_rate"]:
        failures.append("false_positive_match_rate above threshold")
    if report.macro_precision() < THRESHOLDS["min_macro_precision"]:
        failures.append("macro_precision below threshold")
    if report.macro_recall() < THRESHOLDS["min_macro_recall"]:
        failures.append("macro_recall below threshold")
    return (not failures), failures


def save_report(report: EvalReport, path: Path) -> None:
    """TODO: write JSON + markdown so reports are diffable in git."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.__dict__, default=str, indent=2) + "\n", encoding="utf-8")
    path.with_suffix(".md").write_text(report.to_markdown() + "\n", encoding="utf-8")
