"""Audit trail: the hash-chained, append-only record of every decision.

PLACEHOLDER package.

This is what earns the word "controller". Every match, classification, journal
proposal and human approval writes an immutable event:

    event_id, ts, actor, action, subject_ids,
    inputs_hash, rationale, confidence, prev_event_hash

Events are chained by hash, so tampering with history is detectable rather than
merely discouraged. Nothing in the system may UPDATE or DELETE from this log --
corrections are new events that supersede old ones.

Three properties this buys:

  * **Answerability.** For any state, who decided it, why, and on what evidence.
  * **Replayability.** The full decision sequence can be re-derived.
  * **Integrity.** A broken chain proves the log was altered.
"""
