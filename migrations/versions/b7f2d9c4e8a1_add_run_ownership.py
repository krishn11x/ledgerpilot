"""add run ownership to source and reconciliation records

Revision ID: b7f2d9c4e8a1
Revises: 90600b898c7d
Create Date: 2026-08-25 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7f2d9c4e8a1"
down_revision: str | None = "90600b898c7d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in (
        "orders",
        "gateway_txns",
        "payout_batches",
        "bank_txns",
        "matches",
        "breaks",
    ):
        op.add_column(table, sa.Column("run_id", sa.String(length=64), nullable=True))
        op.create_index(f"ix_{table}_run_id", table, ["run_id"], unique=False)


def downgrade() -> None:
    for table in (
        "breaks",
        "matches",
        "bank_txns",
        "payout_batches",
        "gateway_txns",
        "orders",
    ):
        op.drop_index(f"ix_{table}_run_id", table_name=table)
        op.drop_column(table, "run_id")
