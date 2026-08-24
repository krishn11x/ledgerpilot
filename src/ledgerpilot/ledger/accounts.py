"""Chart of accounts for LedgerPilot.

The chart is intentionally minimal and contains only the accounts required
by the payment-reconciliation workflow.

Real deployments can map these fixed LedgerPilot account codes to a
customer-specific chart of accounts through a separate lookup/configuration
layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class AccountType(StrEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


NormalBalance = Literal["debit", "credit"]


@dataclass(frozen=True, slots=True)
class Account:
    """A single general-ledger account."""

    code: str
    name: str
    type: AccountType
    normal_balance: NormalBalance


# Minimum viable chart of accounts required for payment reconciliation.
CHART_OF_ACCOUNTS: dict[str, Account] = {
    "1000": Account(
        "1000",
        "Bank -- Operating",
        AccountType.ASSET,
        "debit",
    ),
    "1100": Account(
        "1100",
        "Accounts Receivable",
        AccountType.ASSET,
        "debit",
    ),
    "1200": Account(
        "1200",
        "Gateway Clearing",
        AccountType.ASSET,
        "debit",
    ),
    "1290": Account(
        "1290",
        "Suspense -- Unidentified Receipts",
        AccountType.ASSET,
        "debit",
    ),
    "2100": Account(
        "2100",
        "Refunds Payable",
        AccountType.LIABILITY,
        "credit",
    ),
    "4000": Account(
        "4000",
        "Revenue",
        AccountType.REVENUE,
        "credit",
    ),
    "4900": Account(
        "4900",
        "Discounts and Write-offs",
        AccountType.EXPENSE,
        "debit",
    ),
    "5100": Account(
        "5100",
        "Payment Processing Fees",
        AccountType.EXPENSE,
        "debit",
    ),
    "5110": Account(
        "5110",
        "Processing Fee Tax (GST)",
        AccountType.EXPENSE,
        "debit",
    ),
    "5200": Account(
        "5200",
        "Chargeback Expense",
        AccountType.EXPENSE,
        "debit",
    ),
    "5300": Account(
        "5300",
        "FX Gain / (Loss)",
        AccountType.EXPENSE,
        "debit",
    ),
}


# Convenience aliases used by posting rules.
# Keeping these aliases makes accounting rules readable and avoids
# scattering magic account numbers throughout the code.
BANK = "1000"
AR = "1100"
GATEWAY_CLEARING = "1200"
SUSPENSE = "1290"
REFUNDS_PAYABLE = "2100"
REVENUE = "4000"
WRITE_OFF = "4900"
PROCESSING_FEES = "5100"
FEE_TAX = "5110"
CHARGEBACK_EXPENSE = "5200"
FX_GAIN_LOSS = "5300"


def get_account(code: str) -> Account:
    """Return an account by code.

    Raises:
        KeyError: If the supplied account code is not present in the chart.
    """
    try:
        return CHART_OF_ACCOUNTS[code]
    except KeyError as exc:
        known = ", ".join(sorted(CHART_OF_ACCOUNTS))
        raise KeyError(
            f"unknown account code {code!r} (known: {known})"
        ) from exc