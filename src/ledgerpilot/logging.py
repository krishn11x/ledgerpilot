"""Structured logging setup.

Console renderer for local development, JSON for anything deployed. Every log
line downstream should carry a ``run_id`` so a reconciliation run can be
reconstructed from logs alone.

Usage::

    from ledgerpilot.logging import get_logger
    log = get_logger(__name__)
    log.info("recon.pass.complete", pass_name="exact", matched=1204)
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from ledgerpilot.config import settings

_configured = False


def configure_logging() -> None:
    """Install the structlog pipeline. Idempotent."""
    global _configured
    if _configured:
        return

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger, configuring the pipeline on first use."""
    configure_logging()
    return structlog.get_logger(name)  # type: ignore[no-any-return]
