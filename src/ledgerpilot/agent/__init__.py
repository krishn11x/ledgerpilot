"""The AI Controller agent layer.

PLACEHOLDER package.

This layer handles only the residual that the deterministic cascade could not
resolve -- roughly 10% of volume. Cost therefore scales with break count, not
transaction count, which is what makes running tens of thousands of
transactions affordable.

**The governing rule: the LLM proposes, deterministic code decides.**

Four jobs where an LLM is genuinely better than code, and nothing else:

  1. Messy narration -> structured entities. Unbounded string variation that
     regex cannot exhaustively cover.
  2. Ambiguity resolution when multiple candidates are plausible and the
     signals are heterogeneous.
  3. Open-set classification of break patterns the taxonomy does not cover.
  4. Controller-language output: root-cause narrative, drafted correspondence.

Graph shape (see ``graph.py``)::

    TRIAGE -> INVESTIGATE <-> [read-only tools]
                  |
              HYPOTHESIZE          structured output + evidence
                  |
                VERIFY             <-- DETERMINISTIC CODE, redoes the arithmetic
                  |                    fails -> loop back, bounded retries
                DECIDE             <-- policy gate, not a model call
                /    \\
              ACT   ESCALATE       interrupt() -> human queue

Hard constraints, enforced structurally rather than by prompting:

  * The agent's tools are read-only. It cannot write to the ledger.
  * VERIFY is code, not a second LLM call. No self-grading.
  * All model output is schema-validated with bounded retries.
  * Per-break token budget; failure to converge escalates rather than spins.
"""
