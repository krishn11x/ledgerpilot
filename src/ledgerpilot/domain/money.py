"""Money as integer minor units.

Design rule, non-negotiable: money is **never** a float. A ``Money`` holds an
integer count of minor units (paise for INR, cents for USD) plus a currency
code. This eliminates an entire class of phantom sub-rupee reconciliation
breaks caused by binary floating point.

    Money(120000, "INR")  ==  INR 1,200.00

Rounding is always explicit. Fee computations like ``2% + INR 3`` produce
fractional minor units, and *which way you round* is a policy decision that
must be stated rather than inherited from the language.

``Decimal`` appears only as an intermediate for exact division and as the
presentation type returned by :meth:`Money.to_major`. Nothing is ever *stored*
as a Decimal -- the integer is the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    Decimal,
    InvalidOperation,
)
from enum import StrEnum
from typing import Self


class Rounding(StrEnum):
    """Explicit rounding policy for fee and FX computations."""

    HALF_UP = "half_up"  # commercial default
    HALF_EVEN = "half_even"  # banker's rounding
    FLOOR = "floor"
    CEIL = "ceil"


#: ``decimal`` mode per policy. Adjacent to the enum so adding a policy is one edit.
_DECIMAL_MODE: dict[Rounding, str] = {
    Rounding.HALF_UP: ROUND_HALF_UP,
    Rounding.HALF_EVEN: ROUND_HALF_EVEN,
    Rounding.FLOOR: ROUND_FLOOR,
    Rounding.CEIL: ROUND_CEILING,
}


# Minor units per major unit, by currency. Not every currency is 100.
MINOR_UNITS_PER_MAJOR: dict[str, int] = {
    "INR": 100,
    "USD": 100,
    "EUR": 100,
    "GBP": 100,
    "JPY": 1,  # yen has no minor unit
    "KWD": 1000,  # dinar has three
}

#: Basis points are per ten-thousand. Named so the literal never appears inline.
BPS_DENOMINATOR = Decimal(10_000)

_ONE = Decimal(1)


def minor_units(currency: str) -> int:
    """Scale factor for ``currency``.

    Raises rather than defaulting to 100: silently assuming two decimal places
    is exactly how JPY and KWD amounts get corrupted by a factor of 100.
    """
    try:
        return MINOR_UNITS_PER_MAJOR[currency]
    except KeyError:
        known = ", ".join(sorted(MINOR_UNITS_PER_MAJOR))
        raise ValueError(f"unsupported currency {currency!r} (known: {known})") from None


def quantize_minor(value: Decimal, rounding: Rounding) -> int:
    """Round an exact ``Decimal`` to a whole number of minor units."""
    return int(value.quantize(_ONE, rounding=_DECIMAL_MODE[rounding]))


@dataclass(frozen=True, slots=True, order=False)
class Money:
    """An exact monetary amount. Immutable, hashable, currency-safe.

    Operations between different currencies raise rather than silently
    coercing -- crossing currencies without an explicit FX conversion is
    always a bug.
    """

    minor: int
    currency: str

    # -- Construction -------------------------------------------------------

    @classmethod
    def zero(cls, currency: str) -> Self:
        """Return a zero amount in ``currency``."""
        minor_units(currency)  # validate the code before minting an amount
        return cls(0, currency)

    @classmethod
    def from_major(cls, amount: Decimal | str | int, currency: str) -> Self:
        """Parse a major-unit amount (``"1200.00"``) into minor units.

        Rejects inputs with more precision than the currency supports: quietly
        truncating ``"1200.005"`` to 120000 loses half a paise per row, which
        aggregates into a real and very hard-to-find break.

        ``float`` is deliberately not accepted -- ``0.1`` is not 0.1.
        """
        scale = minor_units(currency)
        try:
            dec = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        except InvalidOperation:
            raise ValueError(f"not a decimal amount: {amount!r}") from None
        if not dec.is_finite():
            raise ValueError(f"not a finite amount: {amount!r}")

        scaled = dec * scale
        if scaled != scaled.to_integral_value():
            raise ValueError(
                f"{amount} carries more precision than {currency} supports "
                f"({scale} minor units per major unit)"
            )
        return cls(int(scaled), currency)

    # -- Arithmetic ---------------------------------------------------------

    def _same_currency(self, other: Money) -> None:
        """Guard every binary operation. Never coerce, always raise."""
        if not isinstance(other, Money):
            raise TypeError(f"cannot combine Money with {type(other).__name__}")
        if other.currency != self.currency:
            raise ValueError(
                f"currency mismatch: {self.currency} vs {other.currency} -- "
                "cross-currency arithmetic requires an explicit FxRate.convert"
            )

    def __add__(self, other: Money) -> Money:
        """Add, asserting matching currency."""
        self._same_currency(other)
        return Money(self.minor + other.minor, self.currency)

    def __sub__(self, other: Money) -> Money:
        """Subtract, asserting matching currency."""
        self._same_currency(other)
        return Money(self.minor - other.minor, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.minor, self.currency)

    def abs(self) -> Money:
        return Money(abs(self.minor), self.currency)

    def apply_bps(self, bps: int, rounding: Rounding = Rounding.HALF_UP) -> Money:
        """Take ``bps`` basis points of this amount (200 bps == 2%).

        The core primitive for the gateway fee schedule. Division happens in
        ``Decimal`` so the fractional part is exact before rounding is applied.
        """
        exact = Decimal(self.minor) * Decimal(bps) / BPS_DENOMINATOR
        return Money(quantize_minor(exact, rounding), self.currency)

    # -- Presentation -------------------------------------------------------

    def to_major(self) -> Decimal:
        """Exact Decimal in major units, for display and export only."""
        return Decimal(self.minor) / Decimal(minor_units(self.currency))

    def format(self, *, symbol: bool = True) -> str:
        """Locale-ish rendering, e.g. ``"INR 1,200.00"``.

        Decimal places follow the currency, so JPY renders without a point and
        KWD with three.
        """
        scale = minor_units(self.currency)
        places = len(str(scale)) - 1
        sign = "-" if self.minor < 0 else ""
        whole, frac = divmod(abs(self.minor), scale)
        body = f"{whole:,}" if places == 0 else f"{whole:,}.{frac:0{places}d}"
        return f"{self.currency} {sign}{body}" if symbol else f"{sign}{body}"


@dataclass(frozen=True, slots=True)
class FxRate:
    """A dated conversion rate."""

    base: str
    quote: str
    rate: Decimal
    as_of: str  # ISO date

    def convert(self, amount: Money, rounding: Rounding = Rounding.HALF_UP) -> Money:
        """Convert ``amount`` from base to quote currency."""
        if amount.currency != self.base:
            raise ValueError(f"rate {self.base}/{self.quote} cannot convert {amount.currency}")
        exact = amount.to_major() * self.rate * Decimal(minor_units(self.quote))
        return Money(quantize_minor(exact, rounding), self.quote)


def within_tolerance(
    a: Money,
    b: Money,
    *,
    absolute_minor: int,
    relative_bps: int,
) -> bool:
    """True when ``a`` and ``b`` agree within either tolerance band.

    Used by cascade pass 2. Absolute catches rounding dust; relative catches
    proportional drift on large amounts. Either passing is sufficient.

    The relative band is taken against the *larger* of the two amounts, which
    makes the test symmetric -- otherwise ``within_tolerance(a, b)`` and
    ``within_tolerance(b, a)`` could disagree at the boundary.
    """
    a._same_currency(b)
    delta = abs(a.minor - b.minor)
    if delta <= absolute_minor:
        return True
    base = max(abs(a.minor), abs(b.minor))
    allowance = quantize_minor(
        Decimal(base) * Decimal(relative_bps) / BPS_DENOMINATOR, Rounding.HALF_UP
    )
    return delta <= allowance
