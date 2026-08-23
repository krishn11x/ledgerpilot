"""Graph nodes, one module per node.

Split deliberately: each node is independently testable, and the boundary
between "model call" nodes and "deterministic code" nodes is visible in the
file list rather than buried in a function.

    triage       model    classify into the taxonomy, assess materiality
    investigate  model    ReAct loop over read-only tools
    hypothesize  model    structured proposal + confidence + evidence
    verify       CODE     re-derive the arithmetic; reject on mismatch
    decide       CODE     apply the autonomy policy gate
    act          CODE     commit a verified proposal, write journal + audit
    escalate     CODE     interrupt() -> exception queue
"""
