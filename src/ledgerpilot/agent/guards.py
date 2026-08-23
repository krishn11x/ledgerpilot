"""Guardrails on the model layer. PLACEHOLDER -- signatures only.

Four independent limits, each a separate failure mode:

  * **schema** -- output must validate, or retry with the error fed back
  * **budget** -- tokens and steps per break are capped; exhaustion escalates
  * **grounding** -- every cited record id must actually exist
  * **verification** -- proposals are re-checked by code before they count

The last is the important one. An LLM that confidently proposes a wrong match
is the primary risk in this system, and the answer is not a better prompt --
it is that no proposal reaches the ledger without passing arithmetic it cannot
influence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class BudgetExhaustedError(RuntimeError):
    """Raised when a break exceeds its token or step budget. Triggers escalation."""


class SchemaValidationError(ValueError):
    """Model output failed schema validation after all retries."""


class UngroundedClaimError(ValueError):
    """The model cited a record id that does not exist."""


@dataclass(slots=True)
class Budget:
    """Per-break spend tracker. PLACEHOLDER."""

    max_tokens: int
    max_steps: int
    tokens_used: int = 0
    steps_used: int = 0

    def consume(self, *, tokens: int = 0, steps: int = 0) -> None:
        """TODO: increment and raise BudgetExhaustedError past either limit."""
        raise NotImplementedError

    @property
    def exhausted(self) -> bool:
        raise NotImplementedError


def validate_structured_output(raw: str, schema: type[Any]) -> Any:
    """TODO: parse and validate model output; raise SchemaValidationError."""
    raise NotImplementedError


def assert_grounded(proposal: dict[str, Any], known_ids: set[str]) -> None:
    """TODO: every referenced record id must exist. Catches hallucinated ids."""
    raise NotImplementedError


def redact_for_prompt(record: dict[str, Any]) -> dict[str, Any]:
    """TODO: strip PII before it enters a prompt.

    Customer names and emails are not needed to reconcile a payment; amounts,
    dates and references are. Minimising what leaves the process is cheaper
    than auditing what happens to it afterwards.
    """
    raise NotImplementedError
