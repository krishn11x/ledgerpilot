"""Blocking keys and content-hashed match ids. PLACEHOLDER -- signatures only.

Blocking is the performance trick that makes fuzzy matching tractable: instead
of comparing every record against every other (O(n^2)), group records into
buckets that *could* match and compare only within a bucket.
"""

from __future__ import annotations

from datetime import date


def amount_bucket(amount_minor: int, *, width_minor: int = 10_000) -> str:
    """TODO: coarse amount bucket so near-equal amounts land together.

    Must emit the *neighbouring* bucket too when an amount sits near a
    boundary, otherwise tolerance-sized differences straddle buckets and the
    true match is never considered.
    """
    raise NotImplementedError


def date_bucket(value: date, *, window_days: int) -> list[str]:
    """TODO: all day-buckets within +/- window_days of ``value``."""
    raise NotImplementedError


def blocking_keys(*, amount_minor: int, value_date: date, currency: str) -> list[str]:
    """TODO: composite candidate keys for a record."""
    raise NotImplementedError


def match_id_for(legs: list[tuple[str, str]]) -> str:
    """TODO: stable content hash of sorted (record_type, record_id) legs.

    This is what makes the engine idempotent. Must be order-independent and
    must not include timestamps or run ids.
    """
    raise NotImplementedError
