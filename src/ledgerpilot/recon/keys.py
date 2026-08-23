"""Blocking keys and content-hashed match ids. PLACEHOLDER -- signatures only.

Blocking is the performance trick that makes fuzzy matching tractable:
instead of comparing every record against every other (O(n^2)), group records
into buckets that *could* match and compare only within a bucket.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta


def amount_bucket(amount_minor: int, *, width_minor: int = 10_000) -> str:
    """Coarse amount bucket key for grouping near-equal amounts."""
    bucket_idx = amount_minor // width_minor
    return f"AMT-{bucket_idx}"


def date_bucket(value: date, *, window_days: int) -> list[str]:
    """All day-buckets within +/- window_days of value."""
    buckets: list[str] = []
    for offset in range(-window_days, window_days + 1):
        d = value + timedelta(days=offset)
        buckets.append(d.isoformat())
    return buckets


def blocking_keys(*, amount_minor: int, value_date: date, currency: str) -> list[str]:
    """Composite candidate blocking keys for a record."""
    amt_key = amount_bucket(amount_minor)
    keys: list[str] = []
    for d_str in date_bucket(value_date, window_days=2):
        keys.append(f"{currency}:{amt_key}:{d_str}")
    return keys


def match_id_for(legs: list[tuple[str, str]]) -> str:
    """Stable SHA-256 content hash of sorted (record_type, record_id) legs.

    Order-independent and idempotent by construction.
    """
    sorted_legs = sorted(legs, key=lambda x: (x[0], x[1]))
    serialized = "|".join(f"{rtype}:{rid}" for rtype, rid in sorted_legs)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
    return f"MCH-{digest}"
