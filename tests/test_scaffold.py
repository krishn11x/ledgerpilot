"""Scaffold smoke tests: does the architecture actually hold together."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

MODULES = [
    "ledgerpilot",
    "ledgerpilot.config",
    "ledgerpilot.logging",
    "ledgerpilot.cli",
    "ledgerpilot.domain.enums",
    "ledgerpilot.domain.models",
    "ledgerpilot.domain.money",
    "ledgerpilot.domain.policy",
    "ledgerpilot.ingest.loaders",
    "ledgerpilot.ingest.normalize",
    "ledgerpilot.ingest.validate",
    "ledgerpilot.store.db",
    "ledgerpilot.store.tables",
    "ledgerpilot.store.repositories",
    "ledgerpilot.recon.engine",
    "ledgerpilot.recon.rules.exact",
    "ledgerpilot.recon.rules.aggregate",
    "ledgerpilot.ledger.accounts",
    "ledgerpilot.ledger.posting_rules",
    "ledgerpilot.agent.state",
    "ledgerpilot.agent.graph",
    "ledgerpilot.agent.tools",
    "ledgerpilot.audit.events",
    "ledgerpilot.synth.scenarios",
    "ledgerpilot.evaluation.metrics",
    "ledgerpilot.api.main",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module: str) -> None:
    """Every module imports cleanly -- no circular imports in the layering."""
    assert importlib.import_module(module) is not None


def test_domain_imports_nothing_internal() -> None:
    """The domain layer must stay pure.

    This is the load-bearing architectural constraint: it is what allows the
    reconciliation engine to be tested in isolation and to run with the agent
    switched off. Asserting it in a test means it cannot erode quietly.
    """
    import ledgerpilot.domain as domain

    allowed = {"ledgerpilot", "ledgerpilot.domain"}
    for mod in pkgutil.iter_modules(domain.__path__):
        m = importlib.import_module(f"ledgerpilot.domain.{mod.name}")
        for name, value in vars(m).items():
            if name.startswith("__"):
                continue
            origin = getattr(value, "__module__", "") or ""
            if origin.startswith("ledgerpilot."):
                root = ".".join(origin.split(".")[:2])
                assert root in allowed, (
                    f"ledgerpilot.domain.{mod.name} imports {origin} "
                    f"-- the domain layer must import nothing internal"
                )


def test_settings_load() -> None:
    """Configuration resolves without a .env file present."""
    from ledgerpilot.config import get_settings

    s = get_settings()
    assert s.base_currency
    assert 0 <= int(s.autonomy_level) <= 4
    assert 0.0 <= s.auto_approve_min_confidence <= 1.0


def test_break_taxonomy_is_populated() -> None:
    """The taxonomy is the product; it must not be empty or duplicated."""
    from ledgerpilot.domain.enums import BreakType

    values = [b.value for b in BreakType]
    assert len(values) >= 14
    assert len(values) == len(set(values))


def test_scenario_catalogue() -> None:
    """Named scenarios exist, including the ones CI depends on."""
    from ledgerpilot.synth.scenarios import SCENARIOS

    assert {"smoke", "clean", "baseline"} <= set(SCENARIOS)
