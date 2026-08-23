"""Typed application settings, loaded from environment / .env.

Single source of truth for every tunable in the system. Nothing else in the
codebase reads `os.environ` directly -- import `settings` instead so that
tests can override policy without touching the process environment.

All money values are INTEGER MINOR UNITS (paise for INR, cents for USD).
"""

from __future__ import annotations

from enum import IntEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SYNTHETIC_DIR = DATA_DIR / "synthetic"


class AutonomyLevel(IntEnum):
    """How much LedgerPilot is allowed to do without a human.

    Raising this dial is the core "autonomous controller" demo: the same
    dataset produces a very different exception queue at each level.
    """

    DETECT_ONLY = 0
    PROPOSE_ONLY = 1
    AUTO_CLEAR = 2
    AUTO_POST = 3
    AUTO_COMMUNICATE = 4


class Settings(BaseSettings):
    """Runtime configuration. Prefix every env var with ``LP_``."""

    model_config = SettingsConfigDict(
        env_prefix="LP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Application --------------------------------------------------------
    env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["console", "json"] = "console"

    # -- Database -----------------------------------------------------------
    # SQLite by default so the project runs with zero setup. Swap in a
    # ``postgresql+psycopg://`` URL and nothing else changes -- the schema is
    # written against portable SQLAlchemy constructs.
    database_url: str = "sqlite+pysqlite:///./data/ledgerpilot.db"
    db_echo: bool = False
    db_pool_size: int = 5

    # -- Agent --------------------------------------------------------------
    # Read without the LP_ prefix: the Anthropic SDK's own convention.
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    agent_enabled: bool = False
    agent_model_triage: str = "claude-sonnet-5"
    agent_model_escalation: str = "claude-opus-5"
    agent_max_steps: int = 8
    agent_max_retries: int = 2
    agent_token_budget_per_break: int = 20_000

    # -- Reconciliation policy ---------------------------------------------
    base_currency: str = "INR"
    amount_tolerance_minor: int = 100
    amount_tolerance_bps: int = 10
    date_window_days: int = 3
    settlement_lag_days: int = 2
    fuzzy_min_score: float = 0.82
    fuzzy_min_margin: float = 0.05

    # -- Autonomy policy ----------------------------------------------------
    autonomy_level: AutonomyLevel = AutonomyLevel.AUTO_CLEAR
    materiality_threshold_minor: int = 50_000
    auto_approve_min_confidence: float = 0.90

    # -- Gateway fee schedule ----------------------------------------------
    gateway_fee_bps: int = 200
    gateway_fee_flat_minor: int = 300
    gateway_tax_bps: int = 1_800

    # -- Synthetic data -----------------------------------------------------
    synth_seed: int = 42
    synth_order_count: int = 8_000
    synth_period_days: int = 30

    # -- API server ---------------------------------------------------------
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://127.0.0.1:5173"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        """Accept ``a,b,c`` from the environment as well as a JSON list."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def agent_available(self) -> bool:
        """True only when the agent is switched on *and* a key is present."""
        return self.agent_enabled and bool(self.anthropic_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor. Call ``get_settings.cache_clear()`` in tests."""
    return Settings()


settings = get_settings()
