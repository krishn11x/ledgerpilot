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

from dataclasses import dataclass, field
from typing import Any, TypeAlias

from ledgerpilot.domain.enums import BreakType, ExpectedOutcome, ResolutionCategory
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
        """TODO: sum of genuine break rates, excluding noise and timing."""
        raise NotImplementedError


class BreakInjector:
    """Applies a BreakMix and records ground truth. TODO(phase-1)."""

    def __init__(self, *, seed: int) -> None:
        self.seed = seed

    def inject(self, dataset: GeneratedDataset, mix: BreakMix) -> tuple[GeneratedDataset, Labels]:
        """TODO: apply every injector; return mutated data + labels."""
        raise NotImplementedError

    # -- Individual injectors ------------------------------------------------

    def _inject_missing_in_gateway(self, ds: GeneratedDataset, rate: float) -> Labels:
        """TODO: delete gateway txns for paid orders."""
        raise NotImplementedError

    def _inject_fee_variance(self, ds: GeneratedDataset, rate: float) -> Labels:
        """TODO: perturb fee_minor so net no longer matches the schedule.

        Include some one-paise rounding-direction errors -- the realistic and
        genuinely hard case, easy to dismiss as noise and expensive in aggregate.
        """
        raise NotImplementedError

    def _inject_duplicate_payment(self, ds: GeneratedDataset, rate: float) -> Labels:
        """TODO: clone a gateway txn with a new id, same order_ref."""
        raise NotImplementedError

    def _inject_payout_mismatch(self, ds: GeneratedDataset, rate: float) -> Labels:
        """TODO: perturb a bank credit so the batch no longer proves out."""
        raise NotImplementedError

    def _inject_narration_noise(self, ds: GeneratedDataset, rate: float) -> Labels:
        """TODO: strip or corrupt the UTR in narration.

        Not a break in itself -- it forces the fallback path and the agent's
        narration parser, so it is labelled separately from real breaks.
        """
        raise NotImplementedError


def write_ground_truth(labels: Labels, path: str) -> None:
    """TODO: persist the answer key as JSON alongside the dataset."""
    raise NotImplementedError
