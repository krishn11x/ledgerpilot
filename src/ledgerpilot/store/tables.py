"""ORM table definitions.

PLACEHOLDER -- no models implemented yet. This module currently registers no
mappers; it exists so that ``store.db.create_all`` and the Alembic ``env.py``
have a stable import target.

Planned tables, in dependency order:

    Raw / staged source data
        orders, gateway_txns, payout_batches, bank_txns

    Reconciliation output
        recon_runs, matches, match_legs, breaks, break_evidence

    Accounting
        accounts, journal_entries, journal_lines

    Governance
        audit_events            hash-chained, append-only, no UPDATE/DELETE
        agent_runs, agent_steps
        policy_snapshots        what policy was in force for a given run

    Agent durability
        langgraph checkpoints   (see store.checkpoints)

Portability rules for this file:
  * ``JSON`` not ``JSONB``; ``sa.Enum(native_enum=False)`` for portable enums
  * money as ``BigInteger`` minor units -- never Float, never Numeric
  * ``DateTime(timezone=True)`` everywhere; store UTC
  * every foreign key explicitly named via the base naming convention
"""

from __future__ import annotations

from ledgerpilot.store.base import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]

# TODO(phase-1): declare source-record tables (orders, gateway_txns, ...)
# TODO(phase-2): declare matches / breaks / recon_runs
# TODO(phase-4): declare accounts / journal_entries / journal_lines
# TODO(phase-5): declare audit_events with an append-only DB constraint
