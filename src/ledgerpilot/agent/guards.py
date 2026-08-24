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

import json
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
        self.tokens_used += tokens
        self.steps_used += steps
        if self.tokens_used > self.max_tokens or self.steps_used > self.max_steps:
            raise BudgetExhaustedError("budget exhausted")

    @property
    def exhausted(self) -> bool:
        return self.tokens_used >= self.max_tokens or self.steps_used >= self.max_steps


def validate_structured_output(raw: str, schema: type[Any]) -> Any:
    """TODO: parse and validate model output; raise SchemaValidationError."""
    try:
        payload = json.loads(raw)
        if hasattr(schema, "model_validate"):
            return schema.model_validate(payload)
        return schema(**payload)
    except Exception as exc:
        raise SchemaValidationError(str(exc)) from exc


def assert_grounded(proposal: dict[str, Any], known_ids: set[str]) -> None:
    """TODO: every referenced record id must exist. Catches hallucinated ids."""
    refs = proposal.get("matched_record_ids", []) or proposal.get("subject_ids", [])
    missing = [rid for rid in refs if rid not in known_ids]
    if missing:
        raise UngroundedClaimError(f"unknown record ids: {missing}")


def redact_for_prompt(record: dict[str, Any]) -> dict[str, Any]:
    """TODO: strip PII before it enters a prompt.

    Customer names and emails are not needed to reconcile a payment; amounts,
    dates and references are. Minimising what leaves the process is cheaper
    than auditing what happens to it afterwards.
    """
    redacted = dict(record)
    for key in list(redacted):
        lower = key.lower()
        if any(token in lower for token in ("email", "name", "customer", "phone")):
            redacted[key] = "[redacted]"
    return redacted
