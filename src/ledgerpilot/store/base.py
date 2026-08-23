"""SQLAlchemy declarative base and shared column conventions.

The naming convention below is required for Alembic to emit reversible
migrations against PostgreSQL -- without it, autogenerate produces unnamed
constraints that cannot be dropped cleanly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for every LedgerPilot table."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """``created_at`` / ``updated_at``, always stored as timezone-aware UTC."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
