"""Command-line interface.

Deliberately a first-class surface, not an afterthought: the entire demo must be
runnable from the terminal so a broken frontend cannot take the presentation
down with it.

    ledgerpilot info                     show resolved configuration
    ledgerpilot db init                  create tables (dev convenience)
    ledgerpilot generate --scenario X    synthesise data + ground truth
    ledgerpilot recon                    run the deterministic cascade
    ledgerpilot agent                    work the residual queue
    ledgerpilot evaluate --scenario X    print the metrics table
    ledgerpilot serve                    run the API
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ledgerpilot import __version__
from ledgerpilot.config import settings

app = typer.Typer(
    name="ledgerpilot",
    help="AI Finance Controller for autonomous payment reconciliation.",
    no_args_is_help=True,
    add_completion=False,
)
db_app = typer.Typer(help="Database management.", no_args_is_help=True)
app.add_typer(db_app, name="db")

console = Console()


@app.command()
def info() -> None:
    """Show resolved configuration. Verifies the install end to end."""
    table = Table(title=f"LedgerPilot v{__version__}", show_header=False, box=None)
    table.add_column("key", style="cyan")
    table.add_column("value", style="white")

    table.add_row("environment", settings.env)
    table.add_row("database", "postgresql" if settings.is_postgres else "sqlite")
    table.add_row("agent enabled", str(settings.agent_enabled))
    table.add_row("api key present", "yes" if settings.anthropic_api_key else "no")
    table.add_row("agent available", str(settings.agent_available))
    level = settings.autonomy_level
    table.add_row("autonomy level", f"{int(level)} ({level.name})")
    table.add_row("base currency", settings.base_currency)
    table.add_row(
        "materiality",
        f"{settings.materiality_threshold_minor / 100:,.2f} {settings.base_currency}",
    )
    table.add_row("min confidence", f"{settings.auto_approve_min_confidence:.2f}")
    console.print(table)


@db_app.command("init")
def db_init() -> None:
    """Create tables from metadata. Dev convenience; Alembic owns real schemas."""
    from ledgerpilot.store.db import create_all

    create_all()
    console.print("[green]Schema created.[/green]")


@app.command()
def generate(
    scenario: str = typer.Option("baseline", help="Named scenario to materialise."),
    seed: int | None = typer.Option(None, help="Override the scenario seed."),
) -> None:
    """Generate synthetic data with a ground-truth answer key."""
    raise NotImplementedError("Generation lands in phase 1.")


@app.command()
def recon(
    scenario: str = typer.Option("baseline", help="Dataset to reconcile."),
) -> None:
    """Run the deterministic cascade. No LLM involved."""
    raise NotImplementedError("The cascade lands in phase 2.")


@app.command()
def agent(
    limit: int = typer.Option(50, help="Maximum breaks to work."),
) -> None:
    """Work the residual break queue with the AI controller."""
    raise NotImplementedError("The agent lands in phase 5.")


@app.command()
def evaluate(
    scenario: str = typer.Option("baseline", help="Scenario to score."),
    with_agent: bool = typer.Option(False, help="Include the agent layer."),
) -> None:
    """Score a run against ground truth and print the metrics table."""
    raise NotImplementedError("The harness lands in phase 3.")


@app.command()
def serve(
    host: str = typer.Option(None, help="Bind host. Defaults to config."),
    port: int = typer.Option(None, help="Bind port. Defaults to config."),
    reload: bool = typer.Option(True, help="Auto-reload on code changes."),
) -> None:
    """Run the FastAPI server."""
    import uvicorn

    uvicorn.run(
        "ledgerpilot.api.main:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
