# TRIAGE prompt

PLACEHOLDER — not written yet.

## Intended shape

- **Role**: senior reconciliation analyst triaging an unmatched record.
- **Input**: the break context (the record, what the cascade already tried, why each pass failed).
- **Task**: assign one `BreakType`, estimate amount at risk, state a one-line rationale.
- **Output**: structured, schema-validated. No prose outside the schema.

## Guidance to encode

- The full taxonomy with a distinguishing test for each type — the pairs that
  get confused are `SHORT_PAYMENT` vs `FEE_VARIANCE`, and `UNSETTLED` vs
  `TIMING_DIFFERENCE`.
- Prefer `UNCLASSIFIED` over a low-confidence guess. A wrong classification
  routes the break to the wrong team and costs more than an unclassified one.
- Never perform arithmetic; call `check_arithmetic`.
- Cite record ids for every claim.
