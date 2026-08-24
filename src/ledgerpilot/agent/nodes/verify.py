"""VERIFY node -- deterministic verification. No model call."""

from __future__ import annotations

from ledgerpilot.agent.guards import assert_grounded
from ledgerpilot.agent.state import AgentState
from ledgerpilot.ledger.balance import assert_balanced
from ledgerpilot.ledger.posting_rules import propose_entry


async def verify(state: AgentState) -> AgentState:
    """Independently verify the proposed resolution."""

    failures: list[str] = []

    proposal = state.get("proposal", {})
    ctx = state.get("break_context", {})

    known_ids = set(ctx.get("subject_ids", []))

    # 1. Grounding
    try:
        assert_grounded(proposal, known_ids)
    except Exception as exc:
        failures.append(str(exc))

    # 2. Evidence sanity
    matched_ids = proposal.get("matched_record_ids", []) or []

    if len(matched_ids) != len(set(matched_ids)):
        failures.append("duplicate matched record ids")

    # 3. Deterministic journal verification
    break_obj = ctx.get("break_obj")
    suggested_journal = proposal.get("suggested_journal")

    if break_obj is not None:
        expected_journal = propose_entry(break_obj)

        if expected_journal is None:
            if suggested_journal is not None:
                failures.append(
                    "proposal contains a journal where no journal is warranted"
                )
        else:
            try:
                assert_balanced(expected_journal)
            except Exception as exc:
                failures.append(str(exc))

            if suggested_journal is None:
                failures.append("expected journal is missing from proposal")
            else:
                try:
                    if (
                        expected_journal.model_dump()
                        != suggested_journal
                    ):
                        failures.append(
                            "suggested journal does not match deterministic posting rules"
                        )
                except Exception as exc:
                    failures.append(str(exc))

    # 4. Currency consistency
    currency = ctx.get("currency")

    if suggested_journal and currency:
        for line in suggested_journal.get("lines", []):
            if line.get("currency") != currency:
                failures.append("journal currency does not match break currency")
                break

    # 5. High confidence needs evidence
    confidence = float(proposal.get("confidence", 0.0))

    if confidence > 0.9 and len(matched_ids) == 0:
        failures.append(
            "high confidence proposal has no grounded record evidence"
        )

    state["verify_failures"] = failures
    state["verified"] = not failures

    if failures:
        state["retry_count"] = int(state.get("retry_count", 0)) + 1

    return state


def verification_route(state: AgentState) -> str:
    """Route verified proposals to decision; failed proposals retry/escalate."""

    if state.get("verified"):
        return "decide"

    if int(state.get("retry_count", 0)) >= 2:
        return "escalate"

    return "hypothesize"