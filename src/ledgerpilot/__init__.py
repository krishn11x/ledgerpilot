"""LedgerPilot -- AI Finance Controller for autonomous payment reconciliation.

Layer map (import direction is strictly one-way, top depends on bottom):

    api        HTTP surface -- no business logic
    cli        terminal surface -- no business logic
     |
    agent      LLM layer: proposes, never decides
    evaluation ground-truth scoring
     |
    recon      deterministic matching cascade
    ledger     double-entry journal proposals
    audit      hash-chained event log
    synth      synthetic data + ground truth
     |
    ingest     load / normalize / validate
    store      persistence (PostgreSQL-ready)
     |
    domain     pure types -- imports nothing internal

`domain` never imports anything else in this package. That is what lets the
reconciliation engine run with the LLM switched off.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
