"""Break injection with ground-truth labelling. PLACEHOLDER -- signatures only.

Each injector mutates the clean dataset in a specific way and returns a
``GroundTruthLabel`` recording exactly what it did. The labels are the answer
key the evaluation harness scores against.

The critical discipline: an injector must never mutate without labelling. An
unlabelled break shows up as a false positive when the engine correctly finds
it, silently making the metrics wrong -- a bug that flatters the system rather
than exposing it.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from ledgerpilot.domain.enums import BreakType, ExpectedOutcome, ResolutionCategory, TxnDirection
from ledgerpilot.domain.models import BankTxn, GatewayTxn, PayoutBatch
from ledgerpilot.synth.generator import GeneratedDataset


@dataclass(frozen=True, slots=True)
class GroundTruthLabel:
    """The answer key for one injected break.

    Field order mirrors ``store.tables.GroundTruthLabelRow`` column for column,
    so the two can be diffed by eye when either side changes.

    ``scenario`` and ``seed`` are properties of the dataset rather than of the
    individual label, and are repeated on every one. That denormalisation is
    deliberate and matches the table: it lets the evaluation harness filter an
    answer key by scenario and seed without a join, and it means a label found
    on its own still says which dataset it belongs to.

    ``break_type`` is nullable. Not every injector creates a break -- narration
    noise degrades a record while leaving the correct answer a clean match --
    and recording those as ``UNCLASSIFIED`` would inflate the break count with
    cases that have nothing to find. ``None`` means "this record was modified
    and the correct outcome is still a match".

    Labels are **evaluation truth only**. Nothing in ``recon`` or ``agent`` may
    read them: a rule that consulted the answer key would score perfectly and
    measure nothing.
    """

    label_id: str
    scenario: str
    seed: int
    break_type: BreakType | None
    expected_outcome: ExpectedOutcome
    resolution_category: ResolutionCategory
    affected_ids: list[str]
    amount_at_risk_minor: int
    currency: str
    injector: str
    detail: dict[str, str] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        """Column mapping for ``store.GroundTruthRepository.bulk_upsert``.

        The repository takes ``Iterable[Any]`` and calls this method rather than
        importing ``synth``, which would invert the layering -- ``synth`` sits
        above ``store``. Supplying the mapping from this side keeps the
        dependency pointing the right way, at the cost of this method having to
        stay in step with the table by hand.

        Enum members are passed through unconverted. The columns are
        ``sa.Enum(..., values_callable=...)``, so SQLAlchemy's bind processor
        turns each member into its lowercase *value*; converting here as well
        would work by accident (these are ``StrEnum``) but would hide which
        layer owns the representation.

        ``affected_ids`` and ``detail`` are copied. The dataclass is frozen, but
        that freezes the *references* -- handing the live list and dict to the
        ORM would let a later mutation of this label silently change rows that
        are already staged for insert.
        """
        return {
            "label_id": self.label_id,
            "scenario": self.scenario,
            "seed": self.seed,
            "break_type": self.break_type,
            "expected_outcome": self.expected_outcome,
            "resolution_category": self.resolution_category,
            "affected_ids": list(self.affected_ids),
            "amount_at_risk_minor": self.amount_at_risk_minor,
            "currency": self.currency,
            "injector": self.injector,
            "detail": dict(self.detail),
        }

    def to_json_dict(self) -> dict[str, Any]:
        """JSON-serialisable dict representation for ground_truth.json export."""
        return {
            "label_id": self.label_id,
            "scenario": self.scenario,
            "seed": self.seed,
            "break_type": self.break_type.value if self.break_type is not None else None,
            "expected_outcome": self.expected_outcome.value,
            "resolution_category": self.resolution_category.value,
            "affected_ids": list(self.affected_ids),
            "amount_at_risk_minor": self.amount_at_risk_minor,
            "currency": self.currency,
            "injector": self.injector,
            "detail": dict(self.detail),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroundTruthLabel:
        """Reconstruct GroundTruthLabel from a dict (e.g. from ground_truth.json)."""
        bt = data.get("break_type")
        return cls(
            label_id=data["label_id"],
            scenario=data["scenario"],
            seed=int(data["seed"]),
            break_type=BreakType(bt) if bt is not None else None,
            expected_outcome=ExpectedOutcome(data["expected_outcome"]),
            resolution_category=ResolutionCategory(data["resolution_category"]),
            affected_ids=list(data.get("affected_ids", [])),
            amount_at_risk_minor=int(data["amount_at_risk_minor"]),
            currency=data["currency"],
            injector=data["injector"],
            detail=dict(data.get("detail", {})),
        )


#: Every injector returns the labels it produced, so the alias appears everywhere.
Labels: TypeAlias = list[GroundTruthLabel]


@dataclass(slots=True)
class BreakMix:
    """Declared break rates. Fractions of the order population.

    Tuned so the residual pile is large enough for the agent to have visible
    work, but small enough that the deterministic engine still carries the
    volume -- which is the architectural claim being demonstrated.
    """

    missing_in_gateway: float = 0.02
    orphan_payment: float = 0.01
    amount_mismatch: float = 0.02
    short_payment: float = 0.015
    fee_variance: float = 0.04
    unsettled: float = 0.03
    payout_mismatch: float = 0.01
    duplicate_payment: float = 0.008
    refund_unapplied: float = 0.01
    chargeback: float = 0.005
    fx_variance: float = 0.02
    unidentified_credit: float = 0.01
    timing_straddle: float = 0.05  # not a real break; tests the classifier
    narration_noise: float = 0.30  # degrades narration; tests extraction

    def total_break_rate(self) -> float:
        """Return the declared rate of genuine breaks, excluding noise."""
        return sum(
            (
                self.missing_in_gateway,
                self.orphan_payment,
                self.amount_mismatch,
                self.short_payment,
                self.fee_variance,
                self.unsettled,
                self.payout_mismatch,
                self.duplicate_payment,
                self.refund_unapplied,
                self.chargeback,
                self.fx_variance,
                self.unidentified_credit,
            )
        )


class BreakInjector:
    """Applies a BreakMix and records ground truth. TODO(phase-1)."""

    def __init__(self, *, seed: int) -> None:
        self.seed = seed
        self._rng = random.Random(seed)

    def inject(self, dataset: GeneratedDataset, mix: BreakMix) -> tuple[GeneratedDataset, Labels]:
        """Apply declared mutations and return ground truth labels."""
        self._rng = random.Random(self.seed)
        labels: Labels = []
        for injector, rate in (
            (self._inject_fee_variance, mix.fee_variance),
            (self._inject_missing_in_gateway, mix.missing_in_gateway),
            (self._inject_unsettled, mix.unsettled),
            (self._inject_duplicate_payment, mix.duplicate_payment),
            (self._inject_payout_mismatch, mix.payout_mismatch),
            (self._inject_narration_noise, mix.narration_noise),
        ):
            if rate > 0.0:
                labels.extend(injector(dataset, rate))
        return dataset, labels

    # -- Individual injectors ------------------------------------------------

    def _inject_missing_in_gateway(self, ds: GeneratedDataset, rate: float) -> Labels:
        """Remove captured transactions while preserving their payout settlement.

        The missing record is deliberately removed only from a payout that has
        at least two transactions.  The payout and its bank credit are reduced
        by the removed transaction's net amount; otherwise this injector would
        accidentally manufacture an unlabelled ``PAYOUT_MISMATCH`` alongside
        the intended order-to-gateway presence break.
        """
        candidates = self._settled_base_currency_candidates(ds)
        labels: Labels = []

        for txn, payout, bank in self._select(candidates, rate):
            ds.gateway_txns.remove(txn)
            self._replace_payout(
                ds,
                payout.model_copy(
                    update={
                        "expected_net_minor": payout.expected_net_minor - txn.net_minor,
                        "txn_count": payout.txn_count - 1,
                    }
                ),
            )
            self._replace_bank(
                ds,
                bank.model_copy(update={"amount_minor": bank.amount_minor - txn.net_minor}),
            )
            labels.append(
                GroundTruthLabel(
                    label_id=f"GT-MISSING-GATEWAY-{txn.txn_id}",
                    scenario=ds.scenario,
                    seed=ds.seed,
                    break_type=BreakType.MISSING_IN_GATEWAY,
                    expected_outcome=ExpectedOutcome.UNMATCHED,
                    resolution_category=ResolutionCategory.INVESTIGATE,
                    affected_ids=self._affected_ids(txn, payout, bank),
                    amount_at_risk_minor=txn.gross_minor,
                    currency=txn.currency,
                    injector="missing_in_gateway",
                    detail={
                        "removed_gateway_txn_id": txn.txn_id,
                        "order_id": txn.order_ref or "",
                        "payout_resynchronised": "true",
                    },
                )
            )

        return labels

    def _inject_fee_variance(self, ds: GeneratedDataset, rate: float) -> Labels:
        """Perturb a fee by one minor unit while leaving the captured net fixed."""
        labels: Labels = []
        for txn, payout, bank in self._select(self._settled_base_currency_candidates(ds), rate):
            replacement = txn.model_copy(
                update={
                    "fee_minor": txn.fee_minor + 1,
                    "net_minor": txn.net_minor - 1,
                }
            )
            self._replace_gateway_txn(ds, replacement)
            self._replace_payout(
                ds,
                payout.model_copy(update={"expected_net_minor": payout.expected_net_minor - 1}),
            )
            self._replace_bank(
                ds,
                bank.model_copy(update={"amount_minor": bank.amount_minor - 1}),
            )
            labels.append(
                GroundTruthLabel(
                    label_id=f"GT-FEE-VARIANCE-{txn.txn_id}",
                    scenario=ds.scenario,
                    seed=ds.seed,
                    break_type=BreakType.FEE_VARIANCE,
                    expected_outcome=ExpectedOutcome.MATCHED_WITH_EXCEPTION,
                    resolution_category=ResolutionCategory.INVESTIGATE,
                    affected_ids=self._affected_ids(txn, payout, bank),
                    amount_at_risk_minor=1,
                    currency=txn.currency,
                    injector="fee_variance",
                    detail={
                        "gateway_txn_id": txn.txn_id,
                        "expected_fee_minor": str(txn.fee_minor),
                        "actual_fee_minor": str(txn.fee_minor + 1),
                    },
                )
            )
        return labels

    def _inject_unsettled(self, ds: GeneratedDataset, rate: float) -> Labels:
        """Leave a captured transaction outside settlement without breaking a batch.

        The transaction remains captured, but is removed from its former payout
        and that payout's corresponding bank credit.  This models a gateway
        capture that has not settled yet while keeping the remaining batch
        arithmetic valid.  Candidates always belong to a multi-transaction
        payout, so no empty payout is created.
        """
        labels: Labels = []
        for txn, payout, bank in self._select(self._settled_base_currency_candidates(ds), rate):
            self._replace_gateway_txn(ds, txn.model_copy(update={"payout_id": None}))
            self._replace_payout(
                ds,
                payout.model_copy(
                    update={
                        "expected_net_minor": payout.expected_net_minor - txn.net_minor,
                        "txn_count": payout.txn_count - 1,
                    }
                ),
            )
            self._replace_bank(
                ds,
                bank.model_copy(update={"amount_minor": bank.amount_minor - txn.net_minor}),
            )
            labels.append(
                GroundTruthLabel(
                    label_id=f"GT-UNSETTLED-{txn.txn_id}",
                    scenario=ds.scenario,
                    seed=ds.seed,
                    break_type=BreakType.UNSETTLED,
                    expected_outcome=ExpectedOutcome.MATCHED_WITH_EXCEPTION,
                    resolution_category=ResolutionCategory.INVESTIGATE,
                    affected_ids=self._affected_ids(txn, payout, bank),
                    amount_at_risk_minor=txn.net_minor,
                    currency=txn.currency,
                    injector="unsettled",
                    detail={
                        "unsettled_gateway_txn_id": txn.txn_id,
                        "former_payout_id": payout.payout_id,
                        "payout_resynchronised": "true",
                    },
                )
            )
        return labels

    def _inject_duplicate_payment(self, ds: GeneratedDataset, rate: float) -> Labels:
        """Add a second capture for an order and include it in settlement.

        The duplicate has a new immutable gateway identifier but retains the
        order reference and captured amount.  Updating the payout and bank
        credit keeps the aggregate settlement true, leaving exactly the
        intended two-captures-for-one-order anomaly.
        """
        candidates = self._settled_base_currency_candidates(ds)
        labels: Labels = []

        for index, (txn, payout, bank) in enumerate(self._select(candidates, rate), start=1):
            duplicate_id = f"PAY-DUP-{txn.txn_id.removeprefix('PAY-')}-{index:04d}"
            duplicate = txn.model_copy(update={"txn_id": duplicate_id})
            ds.gateway_txns.append(duplicate)
            self._replace_payout(
                ds,
                payout.model_copy(
                    update={
                        "expected_net_minor": payout.expected_net_minor + duplicate.net_minor,
                        "txn_count": payout.txn_count + 1,
                    }
                ),
            )
            self._replace_bank(
                ds,
                bank.model_copy(
                    update={"amount_minor": bank.amount_minor + duplicate.net_minor}
                ),
            )
            labels.append(
                GroundTruthLabel(
                    label_id=f"GT-DUPLICATE-PAYMENT-{duplicate_id}",
                    scenario=ds.scenario,
                    seed=ds.seed,
                    break_type=BreakType.DUPLICATE_PAYMENT,
                    expected_outcome=ExpectedOutcome.AMBIGUOUS,
                    resolution_category=ResolutionCategory.ESCALATE_HUMAN,
                    affected_ids=[*self._affected_ids(txn, payout, bank), duplicate_id],
                    amount_at_risk_minor=duplicate.gross_minor,
                    currency=duplicate.currency,
                    injector="duplicate_payment",
                    detail={
                        "original_gateway_txn_id": txn.txn_id,
                        "duplicate_gateway_txn_id": duplicate_id,
                        "order_id": txn.order_ref or "",
                        "payout_resynchronised": "true",
                    },
                )
            )

        return labels

    def _settled_base_currency_candidates(
        self, ds: GeneratedDataset
    ) -> list[tuple[GatewayTxn, PayoutBatch, BankTxn]]:
        """Return candidates whose payout has a directly comparable bank credit.

        USD payouts settle into the INR account via the generator's private FX
        helper.  This narrow chunk avoids duplicating that formula by operating
        only on same-currency settlement groups.  The standard generator has
        abundant INR records, and later FX-specific injection owns converted
        payouts.
        """
        payout_by_id = {payout.payout_id: payout for payout in ds.payouts}
        counts_by_payout: dict[str, int] = {}
        for txn in ds.gateway_txns:
            if txn.payout_id is not None:
                counts_by_payout[txn.payout_id] = counts_by_payout.get(txn.payout_id, 0) + 1

        candidates: list[tuple[GatewayTxn, PayoutBatch, BankTxn]] = []
        for txn in ds.gateway_txns:
            if txn.status != "captured" or txn.payout_id is None:
                continue
            if counts_by_payout[txn.payout_id] < 2:
                continue
            payout = payout_by_id[txn.payout_id]
            matching_banks = [
                bank
                for bank in ds.bank_txns
                if bank.direction is TxnDirection.CREDIT
                and bank.value_date == payout.settled_on
                and bank.currency == txn.currency
                and bank.amount_minor == payout.expected_net_minor
            ]
            if len(matching_banks) == 1:
                candidates.append((txn, payout, matching_banks[0]))
        return candidates

    def _select(
        self, candidates: list[tuple[GatewayTxn, PayoutBatch, BankTxn]], rate: float
    ) -> list[tuple[GatewayTxn, PayoutBatch, BankTxn]]:
        """Pick a deterministic, non-empty sample for a positive rate."""
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"break rate must be between 0 and 1, got {rate}")
        if rate == 0.0 or not candidates:
            return []
        # One target per payout keeps every replacement based on a current
        # payout total. Selecting two records from the same batch would make
        # the second replacement overwrite the first adjustment.
        target = min(
            len({payout.payout_id for _, payout, _ in candidates}),
            max(1, round(len(candidates) * rate)),
        )
        selected: list[tuple[GatewayTxn, PayoutBatch, BankTxn]] = []
        seen_payouts: set[str] = set()
        for candidate in self._rng.sample(candidates, k=len(candidates)):
            if candidate[1].payout_id not in seen_payouts:
                selected.append(candidate)
                seen_payouts.add(candidate[1].payout_id)
            if len(selected) == target:
                break
        return selected

    @staticmethod
    def _affected_ids(txn: GatewayTxn, payout: PayoutBatch, bank: BankTxn) -> list[str]:
        """Return the real cross-ledger identifiers touched by an injector."""
        return [
            value
            for value in (txn.order_ref, txn.txn_id, payout.payout_id, bank.bank_txn_id)
            if value is not None
        ]

    @staticmethod
    def _replace_payout(ds: GeneratedDataset, replacement: PayoutBatch) -> None:
        """Replace one immutable payout by primary key."""
        for index, payout in enumerate(ds.payouts):
            if payout.payout_id == replacement.payout_id:
                ds.payouts[index] = replacement
                return
        raise LookupError(f"payout not found: {replacement.payout_id}")

    @staticmethod
    def _replace_gateway_txn(ds: GeneratedDataset, replacement: GatewayTxn) -> None:
        """Replace one immutable gateway transaction by primary key."""
        for index, txn in enumerate(ds.gateway_txns):
            if txn.txn_id == replacement.txn_id:
                ds.gateway_txns[index] = replacement
                return
        raise LookupError(f"gateway transaction not found: {replacement.txn_id}")

    @staticmethod
    def _replace_bank(ds: GeneratedDataset, replacement: BankTxn) -> None:
        """Replace one immutable bank line by primary key."""
        for index, bank in enumerate(ds.bank_txns):
            if bank.bank_txn_id == replacement.bank_txn_id:
                ds.bank_txns[index] = replacement
                return
        raise LookupError(f"bank transaction not found: {replacement.bank_txn_id}")

    def _inject_payout_mismatch(self, ds: GeneratedDataset, rate: float) -> Labels:
        """Perturb a bank credit while leaving its payout calculation intact."""
        labels: Labels = []
        for txn, payout, bank in self._select(self._settled_base_currency_candidates(ds), rate):
            magnitude = max(1, min(10_000, bank.amount_minor // 100))
            delta = magnitude if self._rng.choice((True, False)) else -magnitude
            if bank.amount_minor + delta <= 0:
                delta = magnitude
            self._replace_bank(
                ds,
                bank.model_copy(update={"amount_minor": bank.amount_minor + delta}),
            )
            labels.append(
                GroundTruthLabel(
                    label_id=f"GT-PAYOUT-MISMATCH-{bank.bank_txn_id}",
                    scenario=ds.scenario,
                    seed=ds.seed,
                    break_type=BreakType.PAYOUT_MISMATCH,
                    expected_outcome=ExpectedOutcome.MATCHED_WITH_EXCEPTION,
                    resolution_category=ResolutionCategory.INVESTIGATE,
                    affected_ids=self._affected_ids(txn, payout, bank),
                    amount_at_risk_minor=abs(delta),
                    currency=bank.currency,
                    injector="payout_mismatch",
                    detail={
                        "bank_txn_id": bank.bank_txn_id,
                        "expected_amount_minor": str(bank.amount_minor),
                        "actual_amount_minor": str(bank.amount_minor + delta),
                    },
                )
            )
        return labels

    def _inject_narration_noise(self, ds: GeneratedDataset, rate: float) -> Labels:
        """Strip settlement references without changing the underlying credit."""
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"break rate must be between 0 and 1, got {rate}")
        if rate == 0.0 or not ds.bank_txns:
            return []

        target = max(1, round(len(ds.bank_txns) * rate))
        selected = self._rng.sample(ds.bank_txns, k=min(target, len(ds.bank_txns)))
        labels: Labels = []
        for bank in selected:
            noisy = bank.model_copy(
                update={
                    "narration": (
                        f"{bank.currency} MERCHANT CREDIT "
                        f"{bank.value_date.isoformat()}"
                    )
                }
            )
            self._replace_bank(ds, noisy)
            labels.append(
                GroundTruthLabel(
                    label_id=f"GT-NARRATION-NOISE-{bank.bank_txn_id}",
                    scenario=ds.scenario,
                    seed=ds.seed,
                    break_type=None,
                    expected_outcome=ExpectedOutcome.MATCHED,
                    resolution_category=ResolutionCategory.NONE,
                    affected_ids=[bank.bank_txn_id],
                    amount_at_risk_minor=0,
                    currency=bank.currency,
                    injector="narration_noise",
                    detail={"bank_txn_id": bank.bank_txn_id},
                )
            )
        return labels


def write_ground_truth(labels: Labels, path: str) -> None:
    """Persist the answer key as indented JSON alongside a dataset."""
    from pathlib import Path

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([label.to_json_dict() for label in labels], indent=2) + "\n",
        encoding="utf-8",
    )
