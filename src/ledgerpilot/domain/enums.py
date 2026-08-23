"""The shared vocabulary of the system.

These enums are the contract between every layer: the deterministic engine
emits them, the agent classifies into them, the API serialises them, and the
frontend renders them. Adding a break type means touching this file first.

Values are lowercase strings so they are stable across JSON, SQL and the UI.
"""

from __future__ import annotations

from enum import StrEnum


class TxnDirection(StrEnum):
    """Direction of a bank statement line."""

    CREDIT = "credit"
    DEBIT = "debit"


class RunStatus(StrEnum):
    """Lifecycle of a single reconciliation run."""

    PENDING = "pending"
    RUNNING = "running"
    AGENT_WORKING = "agent_working"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class MatchMethod(StrEnum):
    """Which cascade pass produced a match.

    Ordered from most to least certain. Recorded on every match so the audit
    trail can answer "why do we believe these records belong together".
    """

    EXACT_REFERENCE = "exact_reference"  # pass 1: hard key join
    TOLERANCE = "tolerance"  # pass 2: amount + date window
    FUZZY_SCORE = "fuzzy_score"  # pass 3: multi-feature scoring
    AGGREGATE_PAYOUT = "aggregate_payout"  # pass 4: N:1 via payout ref
    AGGREGATE_SUBSET_SUM = "aggregate_subset_sum"  # pass 4 fallback
    AGENT_PROPOSED = "agent_proposed"  # pass 5: LLM, then code-verified
    MANUAL = "manual"  # a human decided


class MatchStatus(StrEnum):
    """Whether a match is committed, provisional, or rejected."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class BreakType(StrEnum):
    """The break taxonomy -- the actual product of reconciliation.

    Reconciliation is not "did it match", it is "*why* didn't it match".
    """

    # -- Presence breaks ----------------------------------------------------
    MISSING_IN_GATEWAY = "missing_in_gateway"  # order paid, no gateway txn
    ORPHAN_PAYMENT = "orphan_payment"  # gateway txn, no order
    UNIDENTIFIED_CREDIT = "unidentified_credit"  # bank credit maps to nothing

    # -- Amount breaks ------------------------------------------------------
    AMOUNT_MISMATCH = "amount_mismatch"  # order gross != gateway gross
    SHORT_PAYMENT = "short_payment"  # partial capture
    OVERPAYMENT = "overpayment"  # excess capture
    FEE_VARIANCE = "fee_variance"  # net != gross - expected fee
    FX_VARIANCE = "fx_variance"  # conversion delta

    # -- Settlement breaks --------------------------------------------------
    UNSETTLED = "unsettled"  # captured, never paid out
    PAYOUT_MISMATCH = "payout_mismatch"  # batch total != bank credit

    # -- Lifecycle breaks ---------------------------------------------------
    DUPLICATE_PAYMENT = "duplicate_payment"  # two captures, one order
    REFUND_UNAPPLIED = "refund_unapplied"  # reversal not reflected
    CHARGEBACK = "chargeback"  # disputed and clawed back

    # -- Not actually broken -------------------------------------------------
    TIMING_DIFFERENCE = "timing_difference"  # in transit across cutoff

    # -- Open set -----------------------------------------------------------
    UNCLASSIFIED = "unclassified"  # rules found nothing; agent's turn


class BreakSeverity(StrEnum):
    """Triage priority. Derived from amount at risk and break type."""

    INFO = "info"  # e.g. timing differences
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"  # above materiality, or suspected duplicate/fraud


class BreakStatus(StrEnum):
    """Workflow state of a break -- drives the exception queue."""

    OPEN = "open"
    INVESTIGATING = "investigating"  # agent is working it
    PENDING_APPROVAL = "pending_approval"  # LangGraph interrupted; human's turn
    RESOLVED_AUTO = "resolved_auto"  # cleared within policy, no human
    RESOLVED_MANUAL = "resolved_manual"  # a human approved it
    WRITTEN_OFF = "written_off"
    REJECTED = "rejected"  # human declined the proposal
    ESCALATED = "escalated"  # out of the agent's remit


class DecisionActor(StrEnum):
    """Who made a decision. Never nullable in the audit log."""

    RULE_ENGINE = "rule_engine"
    AGENT = "agent"
    HUMAN = "human"
    SYSTEM = "system"


class DecisionAction(StrEnum):
    """What a human or the agent did to a break."""

    APPROVE = "approve"
    REJECT = "reject"
    REASSIGN = "reassign"
    WRITE_OFF = "write_off"
    ESCALATE = "escalate"
    COMMENT = "comment"


class JournalEntryStatus(StrEnum):
    """Lifecycle of a proposed double-entry posting."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    POSTED = "posted"
    VOIDED = "voided"


# ---------------------------------------------------------------------------
# Ground-truth vocabulary
#
# Written by the synthetic generator, read by the evaluation harness. It lives
# here rather than in ``synth`` because both sides must agree on it, and
# because a label the harness cannot interpret is a silently wrong metric.
# ---------------------------------------------------------------------------


class ExpectedOutcome(StrEnum):
    """What reconciliation *should* conclude about a case.

    This is the answer to "match or no match", with the two honest middle
    cases spelled out: a case can be correctly matched and still carry a
    break, and a case can be genuinely ambiguous, where escalating is the
    right answer and guessing is the wrong one.
    """

    MATCHED = "matched"  # links exist and are clean
    MATCHED_WITH_EXCEPTION = "matched_with_exception"  # links exist, break remains
    UNMATCHED = "unmatched"  # no counterpart exists at all
    AMBIGUOUS = "ambiguous"  # several plausible counterparts; must escalate


class ResolutionCategory(StrEnum):
    """The disposition a correct system should reach for a case.

    Separate from :class:`BreakStatus`, which is where a break *is*. This is
    where it *ought to end up*, which is what makes it scorable.
    """

    NONE = "none"  # nothing to resolve; a clean match
    AUTO_CLEAR = "auto_clear"  # inside tolerance, clear without a human
    PROPOSE_JOURNAL = "propose_journal"  # needs a posting to close it out
    INVESTIGATE = "investigate"  # agent should reason about it
    ESCALATE_HUMAN = "escalate_human"  # always a human: duplicates, chargebacks
    WRITE_OFF = "write_off"  # immaterial residue
    NO_ACTION = "no_action"  # timing only; resolves itself next period
