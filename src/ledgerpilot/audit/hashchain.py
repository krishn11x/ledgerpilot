"""Hash chaining and integrity verification. PLACEHOLDER -- signatures only.

Each event's hash covers its own content plus the previous event's hash, so
altering any historical event invalidates every hash after it. Cheap to
compute, cheap to verify, and impossible to fake without replacing the whole
tail of the log.

Not a blockchain and not trying to be -- a single-writer hash chain is the
right amount of machinery for a tamper-*evident* internal control.
"""

from __future__ import annotations

from typing import Any

GENESIS_HASH = "0" * 64


def canonical_json(payload: dict[str, Any]) -> str:
    """TODO: deterministic serialisation -- sorted keys, no whitespace, UTC.

    Determinism is the whole requirement: the same logical event must always
    produce the same bytes, or verification produces false alarms.
    """
    raise NotImplementedError


def hash_event(payload: dict[str, Any], prev_hash: str) -> str:
    """TODO: sha256(canonical_json(payload) + prev_hash), hex-encoded."""
    raise NotImplementedError


def verify_chain(events: list[Any]) -> tuple[bool, int | None]:
    """TODO: return (intact, first_broken_index).

    Surfaced in the UI as a green/red integrity badge on the audit log -- an
    auditor can confirm the log has not been edited without reading it.
    """
    raise NotImplementedError
