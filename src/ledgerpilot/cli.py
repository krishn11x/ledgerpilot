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

from pathlib import Path

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
    from sqlalchemy import inspect

    from ledgerpilot.store.db import create_all, get_engine

    create_all()
    engine = get_engine()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if not tables:
        console.print("[red]Database initialization failed: zero tables found.[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]Schema created ({len(tables)} tables).[/green]")


@app.command()
def generate(
    scenario: str = typer.Option("baseline", help="Named scenario to materialise."),
    seed: int | None = typer.Option(None, help="Override the scenario seed."),
) -> None:
    """Generate synthetic data with a ground-truth answer key."""
    from ledgerpilot.synth.scenarios import materialize

    try:
        written = materialize(scenario, seed=seed)
        console.print(f"[green]Materialised scenario '{scenario}' successfully.[/green]")
        table = Table(title=f"Scenario: {scenario}", show_header=True)
        table.add_column("Type", style="cyan")
        table.add_column("Path", style="white")
        for key, path in written.items():
            table.add_row(key, path)
        console.print(table)
    except KeyError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]Generation failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def ingest(
    scenario: str = typer.Option("baseline", help="Named scenario to ingest."),
    data_dir: Path | None = typer.Option(
        None, "--dir", help="Directory containing CSV files to ingest. Overrides --scenario."
    ),
) -> None:
    """Ingest CSV files into the database with validation and quarantine handling."""
    import json
    import uuid
    from datetime import UTC, datetime

    from ledgerpilot.config import SYNTHETIC_DIR
    from ledgerpilot.ingest.loaders import (
        BANK_COLUMNS,
        GATEWAY_COLUMNS,
        ORDER_COLUMNS,
        PAYOUT_COLUMNS,
        read_rows,
        to_bank_txn,
        to_gateway_txn,
        to_order,
        to_payout,
    )
    from ledgerpilot.ingest.validate import (
        validate_bank_txns,
        validate_gateway_txns,
        validate_orders,
        validate_payouts,
    )
    from ledgerpilot.store.db import create_all, session_scope
    from ledgerpilot.store.repositories import (
        BankRepository,
        GatewayRepository,
        GroundTruthRepository,
        IngestRunRepository,
        OrderRepository,
        PayoutRepository,
        QuarantineRepository,
    )
    from ledgerpilot.synth.breaks import GroundTruthLabel
    from ledgerpilot.synth.scenarios import materialize

    source_dir = data_dir if data_dir is not None else (SYNTHETIC_DIR / scenario)
    if not source_dir.exists() and data_dir is None:
        console.print(
            f"[yellow]Dataset for '{scenario}' not found at {source_dir}. "
            "Materialising now...[/yellow]"
        )
        materialize(scenario)

    if not source_dir.exists():
        console.print(f"[red]Directory not found: {source_dir}[/red]")
        raise typer.Exit(code=1)

    create_all()

    run_id = f"RUN-{uuid.uuid4().hex[:8]}"
    started_at = datetime.now(UTC)

    with session_scope() as session:
        run_repo = IngestRunRepository(session)
        quarantine_repo = QuarantineRepository(session)
        order_repo = OrderRepository(session)
        gateway_repo = GatewayRepository(session)
        payout_repo = PayoutRepository(session)
        bank_repo = BankRepository(session)
        gt_repo = GroundTruthRepository(session)

        run_repo.start(
            run_id,
            source_dir=str(source_dir),
            started_at=started_at,
            scenario=scenario if data_dir is None else None,
        )

        counts: dict[str, int] = {
            "orders": 0,
            "gateway_txns": 0,
            "payouts": 0,
            "bank_txns": 0,
            "quarantined": 0,
            "ground_truth": 0,
        }

        orders_file = source_dir / "orders.csv"
        if orders_file.exists():
            raw_orders = read_rows(orders_file, expected=ORDER_COLUMNS)
            accepted_orders, report = validate_orders(raw_orders)
            if report.quarantined:
                quarantine_repo.add_many(run_id, report.quarantined)
                counts["quarantined"] += len(report.quarantined)
            orders = [to_order(r) for r in accepted_orders]
            counts["orders"] = order_repo.bulk_upsert(orders)

        gateway_file = source_dir / "gateway_txns.csv"
        if gateway_file.exists():
            raw_gateway = read_rows(gateway_file, expected=GATEWAY_COLUMNS)
            accepted_gateway, report = validate_gateway_txns(raw_gateway)
            if report.quarantined:
                quarantine_repo.add_many(run_id, report.quarantined)
                counts["quarantined"] += len(report.quarantined)
            gateway_txns = [to_gateway_txn(r) for r in accepted_gateway]
            counts["gateway_txns"] = gateway_repo.bulk_upsert(gateway_txns)

        payouts_file = source_dir / "payouts.csv"
        if payouts_file.exists():
            raw_payouts = read_rows(payouts_file, expected=PAYOUT_COLUMNS)
            accepted_payouts, report = validate_payouts(raw_payouts)
            if report.quarantined:
                quarantine_repo.add_many(run_id, report.quarantined)
                counts["quarantined"] += len(report.quarantined)
            payouts = [to_payout(r) for r in accepted_payouts]
            counts["payouts"] = payout_repo.bulk_upsert(payouts)

        bank_file = source_dir / "bank_txns.csv"
        if bank_file.exists():
            raw_bank = read_rows(bank_file, expected=BANK_COLUMNS)
            accepted_bank, report = validate_bank_txns(raw_bank)
            if report.quarantined:
                quarantine_repo.add_many(run_id, report.quarantined)
                counts["quarantined"] += len(report.quarantined)
            bank_txns = [to_bank_txn(r) for r in accepted_bank]
            counts["bank_txns"] = bank_repo.bulk_upsert(bank_txns)

        gt_file = source_dir / "ground_truth.json"
        if gt_file.exists():
            gt_data = json.loads(gt_file.read_text(encoding="utf-8"))
            labels = [GroundTruthLabel.from_dict(d) for d in gt_data]
            counts["ground_truth"] = gt_repo.bulk_upsert(labels)

        run_repo.finish(
            run_id,
            finished_at=datetime.now(UTC),
            counts=counts,
            status="completed",
        )

    console.print(f"[green]Ingest run '{run_id}' completed successfully.[/green]")
    table = Table(title=f"Ingest Summary ({run_id})")
    table.add_column("Source / Metric", style="cyan")
    table.add_column("Count", style="white")
    for key, count in counts.items():
        table.add_row(key, str(count))
    console.print(table)


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
