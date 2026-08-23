"""Canonicalise records so they can be compared across systems.

The interesting function here is ``extract_references``: bank narration is
unstructured vendor text and the payout reference is buried inside it.

    "NEFT-RAZORPAY SOFTWARE PVT LTD-UTR8837261-STLMNT/AUG"
        -> {"utr": "8837261", "provider": "razorpay", "kind": "settlement"}

Regex handles the common shapes cheaply and deterministically. The long tail of
formats is what the agent's narration-parsing tool is for -- an honest division
of labour: rules for the patterns we know, LLM for the ones we don't.

Two rules run through this module:

*Refuse rather than guess.* ``03/04/2026`` and ``1.200`` are not hard problems,
they are underdetermined ones. Picking a reading silently produces a wrong
number that reconciles against nothing, which costs far more to find later than
a rejected row costs now.

*Never mutate in place.* Every function returns a new value. Raw narration is
evidence and has to survive into the audit trail byte-for-byte.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ledgerpilot.domain.models import BankTxn
from ledgerpilot.domain.money import Money, minor_units

# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")


def normalize_narration(raw: str) -> str:
    """Uppercase, drop punctuation, collapse whitespace.

    Must be pure and stable -- it feeds fuzzy scoring, so any change here
    shifts match results and must be reflected in the eval baseline.

    Aggressive on purpose: ``"NEFT-RAZORPAY/UTR8837261"`` and
    ``"neft razorpay utr 8837261"`` should compare equal enough to score well.
    Reference *extraction* uses a gentler pass (see :func:`extract_references`)
    because punctuation carries signal there.
    """
    return _NON_ALNUM_RE.sub(" ", raw.upper()).strip()


def _upper_collapsed(raw: str) -> str:
    """Uppercase and collapse runs of whitespace, keeping punctuation.

    Reference regexes need the separators: ``UTR:8837261`` and ``UTR 8837261``
    are the same token, but ``STLMNT/AUG`` loses its shape without the slash.
    """
    return _WHITESPACE_RE.sub(" ", raw.upper()).strip()


#: ``UTR8837261``, ``UTR: 8837261``, ``UTR NO. 8837261``, ``UTR-8837261``.
_UTR_RE = re.compile(r"\bUTR(?:\s*(?:NO|NUM|NUMBER|REF)\b)?\s*[:#/-]?\s*([A-Z0-9]{6,22})\b")

#: Retrieval reference number -- the card-network side of the same payment.
_RRN_RE = re.compile(r"\bRRN\s*[:#/-]?\s*([A-Z0-9]{6,22})\b")

#: Our own payout batch identifier, if the gateway bothered to include it.
_PAYOUT_RE = re.compile(r"\b(POUT[-_ ]?\d{4,10})\b")

#: Provider keyword -> canonical slug. Longest match wins, so order is by length.
_PROVIDERS: dict[str, str] = {
    "RAZORPAY": "razorpay",
    "CASHFREE": "cashfree",
    "BILLDESK": "billdesk",
    "CCAVENUE": "ccavenue",
    "INSTAMOJO": "instamojo",
    "STRIPE": "stripe",
    "PAYTM": "paytm",
    "PAYU": "payu",
}

#: Narration keyword -> transaction kind. Checked in order; first hit wins.
_KINDS: tuple[tuple[str, str], ...] = (
    ("CHARGEBACK", "chargeback"),
    ("CHRGBK", "chargeback"),
    ("REVERSAL", "reversal"),
    ("REFUND", "refund"),
    ("SETTLEMENT", "settlement"),
    ("SETTLMNT", "settlement"),
    ("STLMNT", "settlement"),
    ("SETTL", "settlement"),
    ("PAYOUT", "settlement"),
    ("MDR", "fee"),
)


def extract_references(narration: str) -> dict[str, str]:
    """Pull UTR / RRN / payout id / provider out of free text via regex.

    Returns only the keys it is confident about. A missing key means "not
    found", never "not present" -- ``synth`` deliberately emits narration with
    the UTR stripped out, and those rows are what force the subset-sum fallback
    and the agent's narration parser.
    """
    text = _upper_collapsed(narration)
    found: dict[str, str] = {}

    if (utr := _UTR_RE.search(text)) is not None:
        found["utr"] = utr.group(1)
    if (rrn := _RRN_RE.search(text)) is not None:
        found["rrn"] = rrn.group(1)
    if (payout := _PAYOUT_RE.search(text)) is not None:
        # Re-canonicalise the separator so POUT_0001 and "POUT 0001" agree.
        found["payout_id"] = re.sub(r"[-_ ]", "-", payout.group(1))

    for keyword, slug in _PROVIDERS.items():
        if keyword in text:
            found["provider"] = slug
            break

    for keyword, kind in _KINDS:
        if keyword in text:
            found["kind"] = kind
            break

    return found


def enrich_bank_txn(txn: BankTxn) -> BankTxn:
    """Return a copy with ``utr`` populated from parsed narration.

    Non-destructive in both directions: an already-populated ``utr`` from the
    bank's own structured column is trusted over anything scraped out of the
    narration text, and the narration itself is never rewritten.
    """
    if txn.utr:
        return txn
    utr = extract_references(txn.narration).get("utr")
    if utr is None:
        return txn
    return txn.model_copy(update={"utr": utr})


# ---------------------------------------------------------------------------
# Amounts
# ---------------------------------------------------------------------------

_AMOUNT_SHAPE_RE = re.compile(r"\d[\d.,]*")
_CURRENCY_NOISE_RE = re.compile(r"(?:INR|USD|EUR|GBP|JPY|KWD|RS\.?|₹|\$|€|£)", re.IGNORECASE)


def _ungroup(digits: str, sep: str | None) -> str:
    """Strip a thousands separator, rejecting malformed grouping.

    Accepts Western groups of three (``1,234,567``) and the Indian lakh/crore
    pattern of trailing three then twos (``12,34,567``). Rejects
    ``1,2,3``, which is not a grouping in any convention and therefore is
    corrupt input rather than a formatting variant.
    """
    if sep is None or sep not in digits:
        if any(char in digits for char in ",."):
            raise ValueError(f"unexpected separator in digit run {digits!r}")
        return digits
    head, *rest = digits.split(sep)
    if not 1 <= len(head) <= 3 or any(len(group) not in (2, 3) for group in rest):
        raise ValueError(f"malformed digit grouping: {digits!r}")
    if rest and len(rest[-1]) != 3:
        raise ValueError(f"malformed digit grouping: {digits!r}")
    return head + "".join(rest)


def normalize_currency_amount(raw: str, currency: str) -> int:
    """``"1,200.50"`` -> ``120050``. Reject ambiguous separators rather than guess.

    Handles Western (``1,200.50``) and European (``1.200,50``) grouping, the
    Indian lakh grouping (``12,34,567.00``), accounting negatives
    (``(1,200.50)``), and a leading currency symbol or code.

    The separator is classified by the length of the digit run after it:

    ==================  ==============  ==================================
    Input (INR, 2 dp)   Reading         Why
    ==================  ==============  ==================================
    ``1,200``           1200.00         3-digit tail cannot be a 2-dp
                                        fraction
    ``1,20``            1.20            2-digit tail cannot be a 3-digit
                                        group
    ``1,234.56``        1234.56         both present; the last one is the
                                        decimal point
    ``1,234`` in KWD    ValueError      3 dp *and* 3-digit groups --
                                        genuinely undecidable
    ==================  ==============  ==================================
    """
    scale = minor_units(currency)
    places = len(str(scale)) - 1

    text = _CURRENCY_NOISE_RE.sub("", raw).strip()
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative, text = True, text[1:-1].strip()
    if text.startswith(("-", "+")):
        negative, text = text[0] == "-", text[1:].strip()

    if not text or _AMOUNT_SHAPE_RE.fullmatch(text) is None:
        raise ValueError(f"not a currency amount: {raw!r}")

    commas, dots = text.count(","), text.count(".")
    decimal_sep: str | None
    if commas and dots:
        decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
    elif commas + dots == 1:
        sep = "," if commas else "."
        tail = len(text) - text.rindex(sep) - 1
        if tail == 3 and places == 3:
            raise ValueError(
                f"ambiguous amount {raw!r} in {currency}: {sep!r} could be a "
                f"thousands separator or a decimal point, and {currency} has "
                "three decimal places either way"
            )
        if tail == places:
            decimal_sep = sep
        elif tail == 3:
            decimal_sep = None  # grouping; there is no fractional part
        else:
            raise ValueError(
                f"ambiguous amount {raw!r} in {currency}: {tail} digit(s) after "
                f"{sep!r} is neither a {places}-place fraction nor a 3-digit group"
            )
    else:
        decimal_sep = None  # no separators, or grouping only

    group_sep = {",": ".", ".": ","}[decimal_sep] if decimal_sep is not None else None
    if decimal_sep is None:
        group_sep = "," if commas else "." if dots else None

    if decimal_sep is None:
        whole, frac = text, ""
    else:
        whole, _, frac = text.rpartition(decimal_sep)
        if not frac.isdigit():
            raise ValueError(f"not a currency amount: {raw!r}")

    cleaned = _ungroup(whole, group_sep)
    if not cleaned.isdigit():
        raise ValueError(f"not a currency amount: {raw!r}")

    try:
        amount = Decimal(f"{cleaned}.{frac}" if frac else cleaned)
    except InvalidOperation:
        raise ValueError(f"not a currency amount: {raw!r}") from None

    money = Money.from_major(-amount if negative else amount, currency)
    return money.minor


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

#: Formats whose field order is unambiguous, tried in order.
_UNAMBIGUOUS_DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d-%B-%Y",
    "%d %B %Y",
    "%b %d %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%B %d, %Y",
)

#: Two readings of the same digits. If both parse, the input is ambiguous.
_DAY_FIRST = "%d{sep}%m{sep}%Y"
_MONTH_FIRST = "%m{sep}%d{sep}%Y"

_NUMERIC_DATE_RE = re.compile(r"^(\d{1,4})([/.-])(\d{1,2})\2(\d{1,4})$")


def parse_flexible_date(raw: str) -> date:
    """Handle the several date formats banks and gateways emit.

    Refuses ambiguous DD/MM vs MM/DD input instead of picking one: ``03/04/2026``
    raises, while ``14/08/2026`` and ``08/14/2026`` both parse, because only one
    reading of each is a real calendar date.

    Two-digit years are rejected outright. There is no non-arbitrary way to
    place ``31/12/49`` in a century, and a date off by a hundred years lands
    outside every reconciliation window.
    """
    text = _WHITESPACE_RE.sub(" ", raw.strip())
    if not text:
        raise ValueError("empty date")

    for fmt in _UNAMBIGUOUS_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    match = _NUMERIC_DATE_RE.match(text)
    if match is None:
        raise ValueError(f"unrecognised date format: {raw!r}")

    first, sep, _, last = match.groups()
    if len(last) != 4:
        if len(first) == 4:
            raise ValueError(f"unrecognised date format: {raw!r}")
        raise ValueError(
            f"two-digit year in {raw!r}: the century is not recoverable, "
            "so the row is quarantined rather than guessed at"
        )

    readings: dict[str, date] = {}
    for label, template in (("day-first", _DAY_FIRST), ("month-first", _MONTH_FIRST)):
        try:
            readings[label] = datetime.strptime(text, template.format(sep=sep)).date()
        except ValueError:
            continue

    if not readings:
        raise ValueError(f"not a valid calendar date: {raw!r}")
    distinct = set(readings.values())
    if len(distinct) > 1:
        day_first, month_first = readings["day-first"], readings["month-first"]
        raise ValueError(
            f"ambiguous date {raw!r}: reads as {day_first.isoformat()} day-first "
            f"or {month_first.isoformat()} month-first -- the source must state "
            "which convention it uses"
        )
    return distinct.pop()
