"""Policy: the rules that decide what happens without a human.

Policy is separated from the engine on purpose. Tolerances, materiality and
the autonomy ladder are *business* decisions that a finance controller should
be able to change without touching matching code, and every decision the
system makes must be traceable back to the policy snapshot in force at the
time.

Nothing here reads configuration. Rates arrive as constructor arguments so the
domain layer stays importable in isolation; the caller is responsible for
sourcing them from ``ledgerpilot.config``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ledgerpilot.domain.enums import BreakSeverity, BreakType
from ledgerpilot.domain.money import BPS_DENOMINATOR, Rounding, quantize_minor, within_tolerance
from ledgerpilot.domain.money import Money as _Money


@dataclass(frozen=True, slots=True)
class TolerancePolicy:
    """How much wobble counts as "the same amount"."""

    absolute_minor: int
    relative_bps: int
    date_window_days: int

    def amount_ok(self, delta_minor: int, base_minor: int) -> bool:
        """True when ``delta_minor`` is inside either tolerance band.

        Delegates to :func:`ledgerpilot.domain.money.within_tolerance` so the
        boundary arithmetic has exactly one definition. Currency is irrelevant
        to the comparison, so a placeholder code is used for both sides.
        """
        currency = "INR"
        base = abs(base_minor)
        return within_tolerance(
            _Money(base, currency),
            _Money(base + abs(delta_minor), currency),
            absolute_minor=self.absolute_minor,
            relative_bps=self.relative_bps,
        )


@dataclass(frozen=True, slots=True)
class FeeBreakdown:
    """The three derived amounts for one captured transaction.

    Returned as a unit because computing them separately is how callers end up
    with a net that does not equal gross minus the other two.
    """

    gross_minor: int
    fee_minor: int
    tax_minor: int
    net_minor: int


@dataclass(frozen=True, slots=True)
class FeeSchedule:
    """Expected gateway fee, so FEE_VARIANCE can be computed rather than guessed.

    Rounding order matters here and is a real source of one-paise breaks: fee
    first then tax, each rounded, is not the same as rounding once at the end.
    This class rounds twice, in that order, which is what gateways actually do
    and therefore what the ledger must reproduce.

    The tax is levied on the **fee**, not on the gross -- 1800 bps is India's
    GST rate on the payment processor's service charge. Hence
    :meth:`expected_tax_minor` takes ``fee_minor``.
    """

    bps: int
    flat_minor: int
    tax_bps: int
    rounding: Rounding = Rounding.HALF_UP

    def expected_fee_minor(self, gross_minor: int) -> int:
        """bps of gross, plus the flat component, rounded per policy."""
        variable = quantize_minor(
            Decimal(gross_minor) * Decimal(self.bps) / BPS_DENOMINATOR, self.rounding
        )
        return variable + self.flat_minor

    def expected_tax_minor(self, fee_minor: int) -> int:
        """Tax on the fee (GST), rounded per policy."""
        return quantize_minor(
            Decimal(fee_minor) * Decimal(self.tax_bps) / BPS_DENOMINATOR, self.rounding
        )

    def expected_net_minor(self, gross_minor: int) -> int:
        """gross - fee - tax."""
        fee = self.expected_fee_minor(gross_minor)
        return gross_minor - fee - self.expected_tax_minor(fee)

    def breakdown(self, gross_minor: int) -> FeeBreakdown:
        """All four amounts at once, guaranteed internally consistent."""
        fee = self.expected_fee_minor(gross_minor)
        tax = self.expected_tax_minor(fee)
        return FeeBreakdown(
            gross_minor=gross_minor,
            fee_minor=fee,
            tax_minor=tax,
            net_minor=gross_minor - fee - tax,
        )


@dataclass(frozen=True, slots=True)
class AutonomyPolicy:
    """The autonomy ladder made executable. PLACEHOLDER.

    This is the gate that stands between an agent proposal and a committed
    change. It is deliberately dumb, deterministic and easy to audit.
    """

    level: int
    materiality_threshold_minor: int
    min_confidence: float

    def may_auto_resolve(
        self,
        *,
        break_type: BreakType,
        amount_minor: int,
        confidence: float,
    ) -> bool:
        """TODO: True only when policy permits clearing with no human.

        Requires level >= AUTO_CLEAR, confidence >= min_confidence, amount
        below materiality, and a break type that is not inherently
        human-only (duplicates and chargebacks always escalate).
        """
        if self.level < 2:
            return False
        if confidence < self.min_confidence:
            return False
        if amount_minor >= self.materiality_threshold_minor:
            return False
        return break_type not in (BreakType.DUPLICATE_PAYMENT, BreakType.CHARGEBACK)

    def may_auto_post_journal(self, *, amount_minor: int, confidence: float) -> bool:
        """TODO: True only at level >= AUTO_POST and within limits."""
        return (
            self.level >= 3
            and confidence >= self.min_confidence
            and amount_minor < self.materiality_threshold_minor
        )


def severity_for(break_type: BreakType, amount_minor: int, materiality_minor: int) -> BreakSeverity:
    """TODO: derive triage priority from break type and amount at risk.

    Timing differences are INFO regardless of size; suspected duplicates are
    CRITICAL regardless of size.
    """
    if break_type == BreakType.TIMING_DIFFERENCE:
        return BreakSeverity.INFO
    if break_type in (BreakType.DUPLICATE_PAYMENT, BreakType.CHARGEBACK):
        return BreakSeverity.CRITICAL
    if amount_minor >= materiality_minor:
        return BreakSeverity.CRITICAL
    if break_type in (
        BreakType.AMOUNT_MISMATCH,
        BreakType.PAYOUT_MISMATCH,
        BreakType.FEE_VARIANCE,
        BreakType.SHORT_PAYMENT,
        BreakType.MISSING_IN_GATEWAY,
        BreakType.ORPHAN_PAYMENT,
    ):
        return BreakSeverity.MEDIUM
    if break_type in (BreakType.UNSETTLED, BreakType.UNIDENTIFIED_CREDIT, BreakType.FX_VARIANCE):
        return BreakSeverity.LOW
    return BreakSeverity.LOW
