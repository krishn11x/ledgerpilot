# LedgerPilot

**An AI Finance Controller for autonomous payment reconciliation.**

LedgerPilot reconciles the full payment chain — commerce orders, payment gateway
transactions, gateway settlement batches, and bank statement lines — then
explains, classifies and resolves whatever doesn't tie out.

> **Status: local demo.** The deterministic reconciliation engine, evaluation
> harness, API, and API-backed frontend views are runnable locally. The optional
> LLM agent path and several synthetic break injectors remain under development.

---

## The core architectural bet

**Deterministic engine first. AI on the residual only.**

```
100% of transactions
      │
      ├── ~90%  →  Deterministic matching cascade   (pure Python, no LLM)
      │             reproducible · auditable · free · instant
      │
      └── ~10%  →  AI Controller Agent              (LangGraph + Claude)
                    only the ambiguous / unexplained tail
```

Three reasons this is the right split:

- **Money arithmetic must be verifiable code, not token prediction.** Finance
  teams are right to distrust "the LLM did the math."
- **Cost scales with break count, not transaction count.** Tens of thousands of
  transactions stay affordable to run.
- **Determinism means replayability.** Same input plus same policy produces
  byte-identical output — non-negotiable for anything called a controller.

The rule that follows from this, and that runs through the entire codebase:

> **The LLM proposes. Deterministic code decides.**

Every agent hypothesis is re-verified by arithmetic it cannot influence before it
can affect the ledger. The `VERIFY` node contains no AI at all.

---

## The reconciliation chain

The naive framing is "match orders to payments to bank." The real chain has a
wrinkle that most tools get wrong:

```
Order ──1:1──> Gateway Txn ──N:1──> Payout Batch ──1:1──> Bank Credit
 ₹1,200          ₹1,200 gross          Σ net              one line on
                 −₹27.00 fee           = ₹1,168.14        the statement
                 −₹ 4.86 GST             (1-txn batch)     ₹1,168.14
                 = ₹1,168.14 net
```

Fee schedule: **200 bps + ₹3.00**, plus **1800 bps GST on the fee** (not on the
gross). Both roundings are HALF_UP and applied in that order — fee first, then
tax — because rounding once at the end produces a different answer, and the
one-paise gap it leaves is a real `FEE_VARIANCE` break. A payout batch sums
**net** amounts; fees are already deducted per transaction, so deducting them
again at the batch level double-counts them.

Gateways **settle in batches**. Many transactions roll into a single bank credit,
net of fees, refunds and adjustments. That N:1 aggregate step is where the hard
logic lives, and it's the pass LedgerPilot is built around.

---

## Break taxonomy

Reconciliation isn't "did it match," it's **why didn't it match**. The taxonomy
is the deliverable.

| Break type | Meaning |
|---|---|
| `MISSING_IN_GATEWAY` | Order marked paid, no gateway transaction exists |
| `ORPHAN_PAYMENT` | Gateway transaction with no matching order |
| `UNIDENTIFIED_CREDIT` | Bank credit that maps to no payout |
| `AMOUNT_MISMATCH` | Order gross ≠ gateway gross |
| `SHORT_PAYMENT` / `OVERPAYMENT` | Partial or excess capture |
| `FEE_VARIANCE` | Net ≠ gross − expected fee per the fee schedule |
| `FX_VARIANCE` | Currency conversion delta |
| `UNSETTLED` | Captured but never appeared in a payout |
| `PAYOUT_MISMATCH` | Σ(batch) − fees ≠ bank credit |
| `DUPLICATE_PAYMENT` | Two captures against one order |
| `REFUND_UNAPPLIED` / `CHARGEBACK` | Reversal not reflected upstream |
| `TIMING_DIFFERENCE` | Matched, but straddles the period cutoff — *not a real break* |

That last row matters. Separating "genuinely broken" from "merely in transit" is
what makes the tool usable instead of noisy.

---

## The matching cascade

Each pass consumes what earlier passes couldn't match. Cheapest and most certain
runs first.

| Pass | Name | Strategy |
|---|---|---|
| 0 | **Normalize** | Canonicalise narration, dates, currency → integer minor units; regex out references |
| 1 | **Exact** | Join on a hard key (`order_ref`, `payout_id`, UTR). Confidence 1.0 |
| 2 | **Tolerance** | Amount within ε **and** date within window **and** exactly one candidate |
| 3 | **Fuzzy** | Blocking → multi-feature score → threshold **plus margin** check |
| 4 | **Aggregate** | N:1 payout matching. Reference-led first; bounded subset-sum as fallback |
| 5 | **Residual** | Hand off to the agent |

Two details that carry a lot of weight:

- **Pass 3 requires a confidence *margin*, not just a threshold.** If the top two
  candidates score within 0.05 of each other, the case is ambiguous and escalates
  rather than guessing. This is the primary guard against confidently-wrong
  matches.
- **Pass 4's subset-sum is a fallback, not the main path.** A subset that happens
  to sum correctly isn't proof of a settlement, so subset-sum matches are capped
  below the auto-approve threshold and always get human eyes.

---

## The AI Controller agent

Applied only where an LLM is genuinely better than code:

1. **Messy narration → structured entities.**
   `"NEFT-RAZORPAY SOFTWARE PVT LTD-UTR8837261-STLMNT/AUG"` → `{provider, utr, kind}`.
   Unbounded string variation; regex can't be exhaustive.
2. **Ambiguity resolution** across heterogeneous signals.
3. **Open-set classification** of patterns the taxonomy doesn't cover.
4. **Controller-language output** — root-cause narrative, drafted correspondence.

```
             ┌──────────┐
   residual→ │  TRIAGE  │  classify · assess materiality           [model]
             └────┬─────┘
                  ▼
            ┌─────────────┐   read-only tools:
            │ INVESTIGATE │←→ search_orders · search_gateway       [model]
            └──────┬──────┘   search_bank · fuzzy_candidates
                   │          parse_narration · check_arithmetic
                   ▼
            ┌──────────────┐
            │ HYPOTHESIZE  │  proposal + confidence + evidence     [model]
            └──────┬───────┘
                   ▼
            ┌──────────┐   ◄── DETERMINISTIC. Re-derives the arithmetic.
            │  VERIFY  │        Fails → loop back, bounded retries  [code]
            └────┬─────┘
                 ▼
            ┌──────────┐   policy gate, not a model call
            │  DECIDE  │   auto iff confidence ≥ 0.90 AND < materiality  [code]
            └──┬────┬──┘
               ▼    ▼
           ┌─────┐ ┌──────────┐
           │ ACT │ │ ESCALATE │ → interrupt() → exception queue     [code]
           └─────┘ └──────────┘
```

Constraints enforced **structurally**, not by prompting:

- The agent's tools are read-only. It physically cannot write to the ledger.
- `VERIFY` is code, never a second LLM call — self-grading correlates errors.
- All model output is schema-validated with bounded retries.
- Per-break token and step budgets; failure to converge escalates rather than spins.

**Models:** Claude Sonnet 5 for triage and investigation (high volume, cheap),
Claude Opus 5 for the escalated tail.

---

## Autonomy ladder

One config value, five levels. Raising the dial live is the "autonomous
controller" demo.

| Level | Behaviour |
|---|---|
| **L0** | Detect and classify only |
| **L1** | Propose matches, human approves everything |
| **L2** | Auto-clear below materiality, escalate the rest *(default)* |
| **L3** | L2 + auto-post journal entries |
| **L4** | L3 + draft outbound vendor correspondence |

---

## Journal entries and the self-proving control

Every resolved break produces a *proposed* double-entry posting. The keystone is
the **Gateway Clearing** account:

```
Order captured:   Dr Gateway Clearing    1,200.00
                    Cr Revenue                      1,200.00

Payout settles:   Dr Bank               58,407.00
    (50 × ₹1,200) Dr Processing Fees     1,350.00
                  Dr Processing Fee Tax    243.00
                    Cr Gateway Clearing            60,000.00
```

The GST line is a separate account (`5110`) rather than folded into processing
fees, because input tax credit is reclaimable and the fee is not — merging them
loses information the business needs. `58,407 + 1,350 + 243 = 60,000`.

This yields a **control that proves itself**: the Gateway Clearing balance at
period end must equal the sum of captured-but-unsettled transactions. Any
divergence *is* an unreconciled break — found by the ledger itself, independently
of the matching engine. Two independent mechanisms agreeing is far stronger
evidence than either alone.

**Enforced invariant:** `Σ debits == Σ credits`, checked in integer minor units
before an entry can exist. An unbalanced entry is an error, never a warning.

---

## Audit trail

Every match, classification, proposal and approval writes an immutable event:

```
event_id · ts · actor · action · subject_ids ·
inputs_hash · rationale · confidence · prev_event_hash
```

Events are **hash-chained**, so tampering is detectable rather than merely
discouraged. Nothing may `UPDATE` or `DELETE` this log — corrections are new
events that supersede old ones. This buys three properties: answerability (who
decided, why, on what evidence), replayability, and integrity.

---

## Evaluation harness

The synthetic generator injects breaks from a declared spec **and records the
ground truth**, so accuracy is measured rather than asserted.

| Metric | What it proves |
|---|---|
| Auto-match rate | % cleared with zero human touch |
| Precision / recall per break type | It's actually correct |
| **False-positive match rate** | It doesn't confidently mis-match — **the headline** |
| Value unreconciled | Business framing |
| Mean tokens per break | Cost framing |

The false-positive rate matters most: a tool that mis-matches confidently is
worse than one that escalates often, because a wrong match is silently absorbed
into the ledger while an escalation just costs someone five minutes. CI thresholds
are deliberately asymmetric — false positives are capped an order of magnitude
tighter than the coverage floors.

Named scenarios (`src/ledgerpilot/synth/scenarios.py`):

| Scenario | Purpose |
|---|---|
| `smoke` | 50 orders. Sub-second, for tests |
| `clean` | Zero breaks. Any break found is a false positive |
| `baseline` | 8,000 orders, realistic break mix. Demo + CI benchmark |
| `messy` | Heavy narration corruption. Stresses reference extraction |
| `adversarial` | Many near-identical amounts. Tests that ambiguity escalates |

Everything is seeded, so a match-rate change is always attributable to a code
change and never to data luck.

---

## Repository layout

```
ledgerpilot/
├── pyproject.toml            uv-managed Python project
├── alembic.ini               migrations config (URL read from settings)
├── Makefile                  common tasks
├── data/                     SQLite db + generated CSVs (gitignored)
├── migrations/               Alembic revisions
│
├── src/ledgerpilot/
│   ├── config.py             every tunable, typed. Nothing else reads os.environ
│   ├── logging.py            structlog: console in dev, JSON deployed
│   ├── cli.py                full demo runnable without the frontend
│   │
│   ├── domain/               PURE types. Imports nothing internal
│   │   ├── enums.py            break taxonomy — the shared vocabulary
│   │   ├── money.py            integer minor units. Never float
│   │   ├── models.py           entity shapes
│   │   └── policy.py           tolerances · fee schedule · autonomy gate
│   │
│   ├── ingest/               loaders · normalize · validate (+ quarantine)
│   ├── store/                SQLAlchemy 2.0, PostgreSQL-ready
│   │   ├── db.py               engine + session; the only connection point
│   │   ├── tables.py           ORM models
│   │   ├── repositories.py     narrow data access; read-only surface for agent
│   │   └── checkpoints.py      LangGraph durable state
│   │
│   ├── recon/                DETERMINISTIC ENGINE — no LLM
│   │   ├── engine.py           cascade orchestrator
│   │   ├── keys.py             blocking + content-hashed match ids
│   │   ├── scoring.py          multi-feature scores + margin check
│   │   ├── classify.py         break taxonomy assignment
│   │   └── rules/              exact · tolerance · fuzzy · aggregate
│   │
│   ├── ledger/               accounts · posting_rules · balance invariants
│   ├── agent/                AI LAYER
│   │   ├── graph.py            LangGraph state machine
│   │   ├── state.py            state = the audit record
│   │   ├── tools.py            read-only tool surface
│   │   ├── guards.py           schema · budget · grounding limits
│   │   ├── nodes/              triage · investigate · hypothesize ·
│   │   │                       verify · decide · act · escalate
│   │   └── prompts/            versioned templates, recorded in the audit log
│   │
│   ├── audit/                events · hashchain · trace (evidence chains)
│   ├── synth/                generator · breaks (+ ground truth) · scenarios
│   ├── evaluation/           metrics · harness (+ CI thresholds)
│   └── api/                  FastAPI. NO business logic
│       ├── main.py            app factory
│       ├── errors.py          uniform envelope; 501 for unbuilt endpoints
│       ├── sse.py             live progress streaming
│       └── routers/           health · runs · breaks · matches ·
│                              ledger · audit · metrics · scenarios
│
├── tests/                    scaffold asserts the layering rule holds
└── web/                      Vite + React 19 + TS + Tailwind 4
    └── src/
        ├── api/generated.ts    from OpenAPI. Gitignored, never hand-edited
        ├── lib/                typed client + TanStack Query setup
        ├── components/         AppShell · Sidebar · ui
        └── pages/              Exceptions · BreakDetail · Dashboard ·
                                Ledger · AuditLog
```

### The layering rule

```
api · cli          →  agent · evaluation  →  recon · ledger · audit · synth
                                          →  ingest · store  →  domain
```

Import direction is strictly one-way. `domain` imports nothing internal;
`recon` never imports `agent`. This is what lets the engine run with the LLM
switched off — and `tests/test_scaffold.py` asserts it, so it can't erode quietly.

---

## Getting started

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 20+.
No Docker or PostgreSQL needed — SQLite is the default.

### 1. Backend

```bash
uv sync --all-groups
```

```bash
cp .env.example .env
```

```bash
uv run ledgerpilot info
```

That last command prints the resolved configuration and verifies the install.

### 2. Run the API

```bash
uv run uvicorn ledgerpilot.api.main:app --reload --port 8000
```

- Interactive docs → <http://localhost:8000/docs>
- Health + live policy → <http://localhost:8000/health>

### 3. Frontend

```bash
cd web && npm install
```

```bash
cd web && npm run dev
```

App → <http://localhost:5173>. The Vite dev server proxies `/api` to
`:8000`, so there's a single origin and no CORS in development.

### 4. Generate the typed API client

With the backend running:

```bash
cd web && npm run api:generate
```

Types are derived from the Python Pydantic models via OpenAPI. No request or
response interface is hand-written, so backend drift fails at `tsc` instead of at
runtime.

### 5. Verify

```bash
uv run pytest
```

### 6. Run the deterministic demo

From the repository root:

```bash
uv run ledgerpilot db init
uv run ledgerpilot generate --scenario smoke
uv run ledgerpilot ingest --scenario smoke
uv run ledgerpilot evaluate --scenario clean
```

The dashboard, exception queue, break detail, journal, and audit views read
from the FastAPI endpoints at <http://localhost:5173>.

---

## PostgreSQL

SQLite is the default for zero-setup local dev. The schema uses portable
SQLAlchemy constructs only (`JSON` not `JSONB`, `BigInteger` minor units, no
dialect-specific types), and Alembic runs in batch mode — so switching is a URL
change and nothing else:

```bash
LP_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/ledgerpilot
```

```bash
uv run alembic upgrade head
```

---

## Build phases

| Phase | Deliverable | Gate |
|:--:|---|---|
| 0 | **Scaffold** — structure, config, API skeleton, frontend shell | ✅ **done** |
| 1 | `domain` + `money` + synth generator with ground truth + tables | Money arithmetic tests pass |
| 2 | Cascade passes 0–3 + break classification | Engine clears clean data end to end |
| 3 | Pass 4 aggregate payout matching + evaluation harness | **Metrics table exists** |
| 4 | `ledger` + posting rules + balance invariant | Clearing account proves out |
| 5 | LangGraph agent + verify gate + audit chain | Agent resolves a real break |
| 6 | API endpoints + OpenAPI → TS codegen | Endpoints live, client typed |
| 7 | React Exceptions + Break Detail | Approve resumes the agent graph |
| 8 | Dashboard + Audit Log + autonomy dial | Demo rehearsed |

Phases 1–5 are the project. The frontend is built last on purpose: it's the only
phase that's safe to truncate, so it goes where truncation is survivable.

---

## Conventions

- **Money is `int` minor units.** Never `float`, never `Decimal` in storage.
  `120000` is ₹1,200.00. Rounding is always explicit.
- **Idempotent by construction.** Match ids are content hashes of their legs, so
  re-running a reconciliation can't create duplicates.
- **No silent data loss.** Malformed rows go to quarantine with a reason and are
  reported — never dropped, never fatal.
- **Nothing reads `os.environ`** except `config.py`.
- **Every write pairs with an audit event in the same transaction.** A committed
  change with no audit trail is impossible, not merely unlikely.
- **No unexplained numbers in the UI.** Any confidence score ships with its
  per-feature breakdown.

---

## Configuration

Full list with defaults in [.env.example](.env.example). The values worth knowing:

| Variable | Default | Meaning |
|---|---|---|
| `LP_DATABASE_URL` | `sqlite+pysqlite:///./data/ledgerpilot.db` | Swap for a Postgres URL |
| `ANTHROPIC_API_KEY` | *(blank)* | Required only for the agent layer |
| `LP_AGENT_ENABLED` | `false` | Engine runs fine without it |
| `LP_AUTONOMY_LEVEL` | `2` | The ladder, 0–4 |
| `LP_MATERIALITY_THRESHOLD_MINOR` | `50000` | ₹500.00 — above this always escalates |
| `LP_AUTO_APPROVE_MIN_CONFIDENCE` | `0.90` | Floor for autonomous resolution |
| `LP_FUZZY_MIN_MARGIN` | `0.05` | Top-2 gap below this ⇒ ambiguous ⇒ escalate |
| `LP_GATEWAY_FEE_BPS` | `200` | 2.00% of gross |
| `LP_GATEWAY_FEE_FLAT_MINOR` | `300` | + ₹3.00 per transaction, added after rounding |
| `LP_GATEWAY_TAX_BPS` | `1800` | 18% GST **on the fee**, not on the gross |
| `LP_AMOUNT_TOLERANCE_MINOR` | `100` | ₹1.00 absolute wobble allowed |
| `LP_AMOUNT_TOLERANCE_BPS` | `10` | 0.10% relative wobble allowed |
| `LP_SETTLEMENT_LAG_DAYS` | `2` | Gateway T+2 payout cycle |
| `LP_SYNTH_SEED` | `42` | Fixed seed ⇒ reproducible ground truth |

> **Materiality and confidence thresholds are business policy, not technical
> defaults.** The values above are placeholders — they should be owned by whoever
> is accountable for the ledger.

---

## Security notes

- `.env` is gitignored; `.env.example` contains only placeholders and safe local
  defaults. No real key belongs in either.
- `VITE_*` variables are exposed to the browser by design — never put a secret
  in `web/.env*`. The Anthropic key is server-side only.
- `agent.guards.redact_for_prompt` strips PII before it enters a prompt.
  Reconciling a payment needs amounts, dates and references — not customer names.
- The agent's tool surface has no write method, no SQL passthrough and no shell
  access, so "what if the model does something destructive" is answered by
  construction rather than by prompt instructions.

---

## License

MIT
