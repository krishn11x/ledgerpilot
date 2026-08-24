"""Shared fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# Point tests at an in-memory database before any app module is imported.
os.environ.setdefault("LP_DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("LP_AGENT_ENABLED", "false")
os.environ.setdefault("LP_LOG_LEVEL", "WARNING")
os.environ.setdefault("LP_API_AUTH_TOKEN", "test-token")


@pytest.fixture(scope="session")
def client() -> Iterator[object]:
    """FastAPI test client."""
    from fastapi.testclient import TestClient

    from ledgerpilot.api.main import create_app

    with TestClient(create_app(), headers={"Authorization": "Bearer test-token"}) as c:
        yield c
