"""Chart of accounts. PLACEHOLDER -- codes are fixed, behaviour is not.

Deliberately minimal: only the accounts a payment reconciliation actually
touches. Real deployments map these codes to the customer's own COA via a
lookup table rather than renaming anything here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AccountType(StrEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


@dataclass(frozen=True, slots=True)
class Account:
    code: str
    name: str
    type: AccountType
    normal_balance: str  # "debit" | "credit"


# The minimum viable chart of accounts for three-way reconciliation.
CHART_OF_ACCOUNTS: dict[str, Account] = {
    "1000": Account("1000", "Bank -- Operating", AccountType.ASSET, "debit"),
    "1100": Account("1100", "Accounts Receivable", AccountType.ASSET, "debit"),
    # The pivot account: a receivable from the payment processor.
    "1200": Account("1200", "Gateway Clearing", AccountType.ASSET, "debit"),
    "1290": Account("1290", "Suspense -- Unidentified Receipts", AccountType.ASSET, "debit"),
    "2100": Account("2100", "Refunds Payable", AccountType.LIABILITY, "credit"),
    "4000": Account("4000", "Revenue", AccountType.REVENUE, "credit"),
    "4900": Account("4900", "Discounts and Write-offs", AccountType.EXPENSE, "debit"),
    "5100": Account("5100", "Payment Processing Fees", AccountType.EXPENSE, "debit"),
    "5110": Account("5110", "Processing Fee Tax (GST)", AccountType.EXPENSE, "debit"),
    "5200": Account("5200", "Chargeback Expense", AccountType.EXPENSE, "debit"),
    "5300": Account("5300", "FX Gain / (Loss)", AccountType.EXPENSE, "debit"),
}

# Convenience aliases so posting rules read like accounting, not like magic numbers.
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
    """TODO: lookup with a clear error on unknown codes."""
    raise NotImplementedError
