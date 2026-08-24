"""Hash chaining and audit-log integrity verification.

Each event hash covers the event content plus the previous event hash.
Changing any historical event therefore breaks the chain from that point
forward.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

GENESIS_HASH = "0" * 64


def canonical_json(payload: dict[str, Any]) -> str:
    """Serialize a logical event deterministically."""

    def _default(value: Any) -> Any:
        if isinstance(value, datetime):
            timestamp = (
                value.astimezone(UTC)
                if value.tzinfo is not None
                else value.replace(tzinfo=UTC)
            )
            return timestamp.isoformat().replace("+00:00", "Z")

        if hasattr(value, "value"):
            return value.value

        raise TypeError(
            f"not JSON serialisable: {type(value).__name__}"
        )

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=_default,
    )


def hash_event(payload: dict[str, Any], prev_hash: str) -> str:
    """Return the SHA-256 hash of canonical event content plus prev hash."""

    message = (
        canonical_json(payload) + prev_hash
    ).encode("utf-8")

    return hashlib.sha256(message).hexdigest()


def _event_payload(event: Any) -> dict[str, Any]:
    """Reconstruct the exact logical fields covered by AuditEvent hashing."""

    # AuditEvent dataclass.
    if hasattr(event, "event_id") and hasattr(event, "ts"):
        return {
            "event_id": event.event_id,
            "ts": event.ts,
            "actor": event.actor,
            "actor_id": event.actor_id,
            "action": event.action,
            "subject_ids": list(event.subject_ids),
            "payload": dict(event.payload),
            "rationale": event.rationale,
            "confidence": event.confidence,
            "inputs_hash": event.inputs_hash,
            "prev_event_hash": event.prev_event_hash,
        }

    # Persisted AuditEventRow.
    if hasattr(event, "event_id") and hasattr(event, "timestamp"):
        payload = dict(event.payload or {})

        return {
            "event_id": event.event_id,
            "ts": event.timestamp,
            "actor": event.actor,
            "actor_id": payload.get("actor_id", ""),
            "action": event.event_type,
            "subject_ids": list(
                payload.get("subject_ids", [])
            ),
            "payload": dict(
                payload.get("payload", {})
            ),
            "rationale": payload.get("rationale", ""),
            "confidence": payload.get("confidence"),
            "inputs_hash": payload.get("inputs_hash", ""),
            "prev_event_hash": event.prev_hash,
        }

    raise TypeError(
        f"unsupported audit event type: {type(event).__name__}"
    )


def verify_chain(events: list[Any]) -> tuple[bool, int | None]:
    """Verify the full audit chain.

    Returns:
        ``(True, None)`` when every event is intact.
        ``(False, index)`` for the first broken event.
    """

    prev_hash = GENESIS_HASH

    for index, event in enumerate(events):
        event_hash = (
            getattr(event, "event_hash", None)
            or getattr(event, "hash", "")
        )

        if not event_hash:
            return False, index

        try:
            payload = _event_payload(event)
            expected_hash = hash_event(payload, prev_hash)
        except Exception:
            return False, index

        if expected_hash != event_hash:
            return False, index

        prev_hash = event_hash

    return True, None