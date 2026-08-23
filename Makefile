# ---------------------------------------------------------------------------
# LedgerPilot -- common tasks
#
# Requires: uv (Python), node + npm (frontend)
# ---------------------------------------------------------------------------

.DEFAULT_GOAL := help
.PHONY: help install install-web dev api web db-init migrate migration \
        test lint format typecheck client generate recon evaluate clean

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# -- Setup ------------------------------------------------------------------

install:  ## Install Python dependencies
	uv sync --all-groups

install-web:  ## Install frontend dependencies
	cd web && npm install

# -- Run --------------------------------------------------------------------

api:  ## Run the FastAPI server on :8000
	uv run uvicorn ledgerpilot.api.main:app --reload --port 8000

web:  ## Run the Vite dev server on :5173
	cd web && npm run dev

# -- Database ---------------------------------------------------------------

db-init:  ## Create tables from metadata (dev only)
	uv run ledgerpilot db init

migrate:  ## Apply Alembic migrations
	uv run alembic upgrade head

migration:  ## Autogenerate a migration: make migration m="add breaks"
	uv run alembic revision --autogenerate -m "$(m)"

# -- Quality ----------------------------------------------------------------

test:  ## Run the test suite
	uv run pytest

lint:  ## Lint Python and TypeScript
	uv run ruff check src tests
	cd web && npm run lint

format:  ## Auto-format Python
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck:  ## Type-check both halves
	uv run mypy src
	cd web && npm run typecheck

# -- Codegen ----------------------------------------------------------------

client:  ## Regenerate the TypeScript API client (API must be running)
	cd web && npm run api:generate

# -- Pipeline ---------------------------------------------------------------

generate:  ## Generate synthetic data with ground truth
	uv run ledgerpilot generate --scenario baseline

recon:  ## Run the deterministic reconciliation cascade
	uv run ledgerpilot recon

evaluate:  ## Score against ground truth and print the metrics table
	uv run ledgerpilot evaluate --scenario baseline

# -- Housekeeping -----------------------------------------------------------

clean:  ## Remove caches, build output and generated data
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	rm -rf web/dist web/.vite
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -f data/*.db data/*.db-wal data/*.db-shm
	rm -rf data/synthetic/*.csv data/synthetic/*.json
