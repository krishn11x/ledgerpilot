"""Evaluation harness: prove it works, do not assert it.

PLACEHOLDER package. (Named ``evaluation`` rather than ``eval`` to avoid
shadowing the builtin.)

Because ``synth`` emits ground-truth labels, every claim about LedgerPilot's
accuracy is measurable:

    auto_match_rate           % cleared with zero human touch
    precision / recall        per break type
    false_positive_match_rate wrong matches made confidently  <-- headline
    value_unreconciled        currency amount still open
    escalation_rate           % that needed a human
    mean_agent_cost           tokens and money per resolved break

The metric that matters most is the false-positive match rate. A reconciliation
tool that confidently mis-matches is worse than one that escalates often,
because a wrong match is silently absorbed into the ledger while an escalation
merely costs someone five minutes.
"""
