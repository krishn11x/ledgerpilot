# LedgerPilot

## Overview

LedgerPilot is an AI finance controller for autonomous payment reconciliation.
It connects commerce orders, gateway transactions, payout batches, and bank
statements, then separates deterministic matching from the residual cases that
need human review or a LangGraph-assisted decision path.

> Status: Demo Ready
>
> LedgerPilot is a feature-complete, reproducible local demo of an AI-assisted
> payment reconciliation platform. The verified demo includes deterministic
> reconciliation, LangGraph orchestration, human-in-the-loop decisions,
> double-entry safeguards, audit trails, evaluation, authentication, and a
> React dashboard.
>
> A hosted public deployment is not currently provided. Production deployment
> would additionally require durable checkpoint storage, full identity
> management, rate limiting, and production infrastructure.

## Key capabilities

- Deterministic reconciliation engine with tiered matching passes
- Real LangGraph workflow for ambiguous residual cases
- Human-in-the-loop decision gates
- Synthetic break generators and evaluation harness
- Audit trail and hash-chained event history
- FastAPI backend with typed frontend integration
- React/Vite dashboard and exception views
- Browser smoke verification for the local demo flow

## Demo

### Local demo

```bash
uv sync --all-groups
cp .env.example .env
uv run ledgerpilot info
uv run uvicorn ledgerpilot.api.main:app --reload --port 8000
```

In a second terminal:

```bash
cd web
npm install
npm run dev
```

> A hosted public deployment is not currently provided.
> Localhost URLs such as `http://localhost:8000/docs`, `http://localhost:8000/health`, and `http://localhost:5173` only work after the application is running locally.

### Demo flow

```bash
uv run ledgerpilot db init
uv run ledgerpilot generate --scenario smoke
uv run ledgerpilot ingest --scenario smoke
uv run ledgerpilot evaluate --scenario clean
```

This intentionally exercises the deterministic pipeline, the API layer, and the
frontend views in a controlled local environment.

---

## Why this is interesting

Most payment systems either rely on a brittle rules engine or hand off too much
work to an LLM. LedgerPilot does neither. The design is deliberate:

- deterministic code handles the majority of low-risk matching work
- the AI layer is reserved for ambiguous residuals and explanation
- every decision is grounded in arithmetic and event history
- policy gates prevent silent mis-matches from reaching the ledger
- models used by the optional LLM integration are configurable; the core
  reconciliation and evaluation paths do not require an external LLM service

This creates a practical finance workflow: fast automation for the routine,
human oversight for the edge cases, and evidence for every decision.

---

## Repository navigation

### Architecture and source

- [Core package](src/ledgerpilot)
- [Configuration](src/ledgerpilot/config.py)
- [CLI entrypoints](src/ledgerpilot/cli.py)
- [Deterministic reconciliation engine](src/ledgerpilot/recon/engine.py)
- [Agent graph](src/ledgerpilot/agent/graph.py)
- [Audit and hash chain](src/ledgerpilot/audit)
- [API application factory](src/ledgerpilot/api/main.py)
- [API routers](src/ledgerpilot/api/routers)
- [Frontend app](web)

### Tests and validation

- [Test suite](tests)
- [Agent graph tests](tests/test_agent_graph.py)
- [Break decision API tests](tests/test_break_decision_api.py)
- [E2E demo flow](tests/test_e2e_demo.py)
- [Evaluation harness tests](tests/test_evaluation_harness.py)
- [Security hardening tests](tests/test_security_hardening.py)

### Data and config

- [.env example](.env.example)
- [Web env example](web/.env.example)
- [Synthetic scenarios](src/ledgerpilot/synth/scenarios.py)
- [Evaluation harness](src/ledgerpilot/evaluation/harness.py)
- [API schemas](src/ledgerpilot/api/schemas.py)

---

## Screenshots / Demo

No screenshot assets are currently committed in this repository.
The working demo is best reviewed through the live project flow and the test suite,
including [tests/test_e2e_demo.py](tests/test_e2e_demo.py) and the frontend in [web/src](web/src).

---

## Architecture summary

The project is structured around a disciplined layering model.

- [src/ledgerpilot/domain](src/ledgerpilot/domain) contains pure types and policy
- [src/ledgerpilot/recon](src/ledgerpilot/recon) implements the deterministic matching cascade
- [src/ledgerpilot/ledger](src/ledgerpilot/ledger) enforces posting and balance invariants
- [src/ledgerpilot/agent](src/ledgerpilot/agent) hosts the LangGraph workflow
- [src/ledgerpilot/audit](src/ledgerpilot/audit) records immutable reasoning history
- [src/ledgerpilot/api](src/ledgerpilot/api) exposes the application to the frontend
- [web](web) provides the Vite + React dashboard and exception views

---

## Production limitations

LedgerPilot is currently designed for a controlled local demo and evaluation setup.

- Local SQLite is the default configuration rather than a hosted production database
- LangGraph state is process-scoped through the current checkpoint implementation
- Authentication is shared bearer-token based rather than a full enterprise auth system
- A hosted public deployment is not currently provided
- Production work still needed includes infrastructure, monitoring, environment hardening, and deployment automation

This is a credible working prototype and demo platform, but it is not presented as a fully hosted production deployment.

---

## Security notes

- The project keeps secrets in environment files and expects local operators to manage them responsibly
- The server-side Anthropic key is not part of the browser frontend
- Prompt redaction and read-only tool surfaces are used to reduce model-side risk
- The deterministic ledger logic remains the control layer for money movement

See [src/ledgerpilot/config.py](src/ledgerpilot/config.py) and [src/ledgerpilot/agent/guards.py](src/ledgerpilot/agent/guards.py) for the operational safeguards.

---

## Getting started

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), and Node 20+.

```bash
uv sync --all-groups
cp .env.example .env
uv run ledgerpilot info
```

Start the backend:

```bash
uv run uvicorn ledgerpilot.api.main:app --reload --port 8000
```

Start the frontend:

```bash
cd web
npm install
npm run dev
```

Run the test suite:

```bash
uv run pytest
```

---

## License

MIT
