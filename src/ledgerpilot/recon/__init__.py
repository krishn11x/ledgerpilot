"""Reconciliation engine: the deterministic core.

PLACEHOLDER package.

This is the heart of LedgerPilot and it contains **no LLM calls**. Money
arithmetic must be verifiable code, not token prediction. Roughly 90% of
volume clears here -- reproducibly, instantly, and for free.

The cascade, each pass consuming what earlier passes could not match:

    pass 0  normalize   canonicalise (see ledgerpilot.ingest.normalize)
    pass 1  exact       join on a hard reference key
    pass 2  tolerance   amount within epsilon AND date within window
    pass 3  fuzzy       blocking -> multi-feature score -> threshold + margin
    pass 4  aggregate   N:1 payout matching (ref first, subset-sum fallback)
    pass 5  residual    hand off to ledgerpilot.agent

Two invariants hold across the whole engine:

  * **Idempotent.** Match ids are content hashes of their legs, so re-running
    a run cannot create duplicates.
  * **Deterministic.** Same input plus same policy always produces
    byte-identical output. No wall-clock, no randomness, no set iteration
    order leaking into results.
"""
