"""API request/response schemas.

PLACEHOLDER -- request shapes and envelopes only.

Separate from ``domain.models`` on purpose. Domain types describe reality; API
schemas describe a wire contract that must stay stable for the frontend. Keeping
them apart means a domain refactor does not silently break the TypeScript
client.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from ledgerpilot.domain.enums import BreakStatus, BreakType, DecisionAction

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Standard pagination envelope for every list endpoint."""

    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorEnvelope(BaseModel):
    """Documents the shape produced by ``api.errors``."""

    code: str
    message: str
    detail: object | None = None


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class StartRunRequest(BaseModel):
    """Kick off a reconciliation run."""

    scenario: str | None = Field(
        default=None, description="Named synthetic scenario, or None to use loaded data"
    )
    with_agent: bool = Field(default=False, description="Run the agent on residuals")
    autonomy_level: int | None = Field(
        default=None, ge=0, le=4, description="Override the configured autonomy level"
    )


class BreakDecisionRequest(BaseModel):
    """A human decision on a break. Resumes the interrupted agent graph."""

    action: DecisionAction
    note: str = Field(default="", max_length=2000)
    assignee: str | None = None
    # TODO(phase-7): expected_version, for optimistic concurrency so two
    # reviewers cannot decide the same break twice


class BreakQuery(BaseModel):
    """Exception queue filters."""

    status: BreakStatus | None = None
    break_type: BreakType | None = None
    min_amount_minor: int | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class GenerateScenarioRequest(BaseModel):
    """Generate synthetic data on demand."""

    scenario: str = "baseline"
    seed: int | None = None
    order_count: int | None = Field(default=None, ge=1, le=200_000)


# ---------------------------------------------------------------------------
# Responses -- TODO(phase-6): flesh out as features land
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Liveness and configuration snapshot."""

    status: str
    version: str
    env: str
    database: str
    database_reachable: bool
    agent_available: bool
    autonomy_level: int
