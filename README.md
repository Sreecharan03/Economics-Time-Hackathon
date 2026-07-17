# Meridian — AI Compliance & Schedule-Impact Platform for Data Centre EPC

## What this is

An AI-assisted platform that reads a vendor equipment submittal, checks it against
the project specification, and — when it finds a deviation — deterministically
traces whether that deviation actually threatens a downstream commissioning test
date, using real critical-path schedule logic instead of guesswork.

The chain **spec deviation → affected equipment → procurement package → schedule
activity → commissioning test at risk** is the entire product thesis. No competitor
(BuildSync, Trunk Tools, Procore AI, Autodesk ACC, nPlan, ALICE, CxAlloy) connects
all three domains — each owns one. Everything in this repo exists to make that one
chain real and defensible; nothing is built that doesn't serve it.

Full problem analysis, competitive landscape, and architecture rationale: see the
critical evaluation this project is built from (not checked into this repo).

## Non-goals (explicit scope boundary)

- **Not** an ML schedule predictor. Schedule impact is deterministic CPM
  (forward/backward pass on finish-to-start dependencies), not a trained model.
  ML-based schedule risk (à la nPlan) needs hundreds of thousands of historical
  projects to be credible; we don't have that data and won't pretend otherwise.
- **Not** an autonomous-approval system. Every compliance verdict and every
  drafted RFI is advisory, human-in-the-loop. AIA A201 §3.12.5 preserves
  contractor/engineer responsibility; no AI tool can absorb that liability.
- **Not** a general RAG chatbot over construction documents. Retrieval exists
  for exactly one purpose: finding precedent RFIs for a detected deviation.
- **Not** a knowledge-graph product (yet). Postgres + pgvector models the same
  entity relationships as a property graph would; Neo4j is deferred until
  multi-hop, multi-project queries are the actual bottleneck, not before.

## Architecture

Six services, orchestrated synchronously over HTTP by one gateway. No agent
framework, no message queue (yet) — this is five deterministic-or-narrow steps
per request, not an open-ended agentic task, so a queue would add failure
surface without buying anything at this scale.

```
                        ┌─────────────┐
   client (frontend) ──▶│   gateway   │
                        └──────┬──────┘
                               │ owns the request lifecycle
                               ▼
                    ┌─────────────────────┐
                    │ extraction-service   │  PDF/text in → typed schema out
                    │ (Groq LLM)           │
                    └──────────┬───────────┘
                               ▼
                    ┌─────────────────────┐
                    │ compliance-service   │  deterministic rule engine, NO LLM
                    │ (pure Python)        │  PASS / FAIL / CONFLICT + citation
                    └──────────┬───────────┘
                     ┌─────────┴─────────┐
                     ▼                   ▼
          ┌─────────────────┐  ┌──────────────────┐
          │ schedule-service │  │ retrieval-service │
          │ (pure Python,    │  │ (pgvector          │
          │  CPM fwd/bwd     │  │  similarity search) │
          │  pass, NO LLM)   │  │                    │
          └────────┬─────────┘  └─────────┬──────────┘
                    └───────────┬──────────┘
                                ▼
                     ┌─────────────────────┐
                     │  drafting-service    │  grounded RFI/CAR draft,
                     │  (Groq LLM)          │  cites clause + value +
                     └─────────────────────┘  schedule impact + precedent
```

**The rule that shapes this diagram:** only `extraction-service`, `retrieval-service`
(embedding call), and `drafting-service` touch a model. `compliance-service` and
`schedule-service` are plain, tested Python with no model call in the loop —
because those two produce numbers that feed engineering coordination studies and
commissioning dates, and "usually right" isn't an acceptable bar there.

## Repository layout

```
epc-ai-platform/
├── dataset/                  synthetic Meridian Data Hall 1 project data
│   ├── specs/                 CSI-style guide spec, real ANSI/IEEE thresholds
│   ├── submittals/             equipment_master.json + raw vendor cut-sheet text
│   ├── schedule/                schedule.csv (CPM network) + validate_cpm.py
│   ├── rfis/                    20 synthetic historical RFIs (retrieval corpus)
│   └── gold_set/                 labeled compliance + schedule-propagation truth
│                                  for evals/ to score against
├── services/
│   ├── gateway/
│   ├── extraction-service/
│   ├── compliance-service/
│   ├── schedule-service/
│   ├── retrieval-service/
│   └── drafting-service/
├── frontend/                  Next.js
├── infra/
│   ├── docker-compose.yml      postgres+pgvector + all 6 services + frontend
│   └── db/migrations/           shared schema
├── evals/                     scripts scoring services against dataset/gold_set/*.csv
└── .github/workflows/ci.yml    lint + test each service independently
```

Each service directory has its own `README.md` documenting its single
responsibility and exact request/response contract — read those before touching
that service's code.

## Progress

**Overall: `[███████░░░░░░░░░░░░░]` ~37%**

Weighted by remaining effort, not file count — Phase 0 was real work (dataset
+ validation + architecture) but implementation/testing across 6 services,
the frontend, and integration is the bulk of what's left.

| Component | Weight | Status | Progress |
|---|---|---|---|
| Phase 0 — design, dataset, scaffold | 15% | ✅ Complete | `[████████████████████]` 100% |
| `compliance-service` | 12% | ✅ Engine + API + tests + Docker, verified end-to-end | `[██████████████████░░]` 90% |
| `schedule-service` | 12% | ✅ Engine + API + tests + Docker, verified end-to-end | `[██████████████████░░]` 90% |
| `extraction-service` | 12% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| `retrieval-service` | 12% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| `drafting-service` | 12% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| `gateway` | 12% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| `frontend` | 8% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| Integration + demo polish | 5% | ⬜ Not started | `[░░░░░░░░░░░░░░░░░░░░]` 0% |

**What "done" means for a service** (see [Push/test policy](#pushtest-policy)
below): not just code that runs, but a green pytest suite with deep edge-case
coverage. A service only moves out of "no code" once that bar is cleared.

### `compliance-service` (2026-07-17)

First service implemented. `engine.py` is pure Python (no LLM, no DB, no
network) implementing two check types -- RANGE (numeric, covers both
tolerance-band and minimum-only checks with one code path) and ENUM (exact
string match) -- plus CONFLICT handling for spec-internal contradictions.
`spec_data.py` seeds requirements from `dataset/submittals/equipment_master.json`
rather than a second hand-typed copy. `main.py` is a thin FastAPI wrapper with
no comparison logic of its own.

Test suite: 69 pytest nodes (48 in `test_engine.py`, 21 in `test_api.py`) all
passing, covering all 21 gold-set rows, the full 12-item demo set end-to-end
through the real API, explicit edge cases (bool-as-numeric rejection,
NaN/Inf, unit mismatches, case sensitivity), plus 8 Hypothesis property tests
independently verified to execute **1,892 generated example evaluations**
(counted empirically, not asserted) checked against independently-written
reference formulas, not the implementation restating its own logic.

Verified beyond pytest: built as a real Docker image, run as a real
container, hit over real HTTP for both the FAIL (XFMR-01) and CONFLICT
(ATS-01) cases, and brought up through `docker compose up` itself (not just
manual `docker build`/`run`) before being torn down. One real bug caught in
that process: an `os.environ.get(key, default)` call evaluated its fallback
path eagerly regardless of whether the env var was set, crashing the
container on startup — a bug pytest alone never would have caught, since the
local dev path happened to resolve fine.

Not yet done: Postgres-backed spec-requirement loading (currently the
JSON-file seed, an intentional interim stand-in documented in
`spec_data.py`) and `DATABASE_URL` wiring in `docker-compose.yml`.

### `schedule-service` (2026-07-17)

Second service implemented. `engine.py` is the same algorithm independently
verified by `dataset/schedule/validate_cpm.py` and `validate_propagation.py`
during the gold-set audit -- wrapped for API use, not reimplemented, so the
switchgear-float class of bug found there has exactly one place to hide, not
two. Full forward + backward pass over the *entire* network on every call,
never just the triggering activity's own chain -- that shortcut is precisely
what produced the original 263-vs-273 float error.

Test suite: 65 pytest nodes (52 in `test_engine.py`, 13 in `test_api.py`),
covering the full baseline network against every recorded column in
`schedule.csv`, both seeded gold-set propagation scenarios, explicit edge
cases (cycle detection, dangling predecessors, negative delays, unknown
milestones), plus 4 Hypothesis property tests independently verified to
execute **799 generated example evaluations** against synthetic
linear-chain and parallel-chain (diamond) networks — including a property
proving the exact formula behind the switchgear result generalizes
(shorter-chain float equals the chain-length difference; a delay is only
absorbed up to that float, then slips 1:1 beyond it).

Verified beyond pytest: built as a real Docker image, run as a container,
hit over real HTTP for both scenarios, then brought up alongside
`compliance-service` simultaneously via a single `docker compose up`. One
side effect worth noting, not a bug: delaying the critical-path transformer
by 14 days also *increases* the float on unrelated non-critical chains (e.g.
`ENG-020`'s float grew from 460 to 474) even though their own dates don't
move — correct CPM behavior once the deadline they're measured against
shifts, and only visible because the engine recomputes the whole network
rather than just the triggered chain.

Not yet done: Postgres-backed schedule loading (currently the CSV seed,
same interim-stand-in pattern as `compliance-service`).

### Push/test policy

Code changes to any `services/*/app/` push to GitHub only after that
service's `tests/` suite (target: ~1000+ distinct parametrized edge cases —
boundary values, malformed/missing input, unit mismatches, not just the
golden-path gold-set rows) is written and passing. This is a per-service bar,
not a whole-project one. Docs-only changes (this README, service READMEs)
are exempt and push freely. Local commits are never gated — only `git push`.

This table is updated every push, reflecting real state, not aspiration.
Last updated: 2026-07-17 — gold-set audit (see below), pushed to `origin/main`.

### Gold-set audit (2026-07-17)

A critical re-read of `dataset/gold_set/compliance_gold_set.csv` and
`equipment_master.json` (prompted by "don't think blindly, actually check
it") found and fixed real problems before any service code depended on them:

- `equipment_master.json` had two incompatible shapes (flat fields for
  single-attribute equipment, a differently-shaped `attributes[]` array with
  boolean `pass` for UPS items) — unified to one `attributes[]` shape with a
  consistent `verdict` string on every item.
- `compliance_gold_set.csv`'s `required_value` column mixed clean scalars
  with composite narrative strings (e.g. `"5.75 (+/-7.5%, 5.32-6.18
  acceptable)"`) for the tolerance-band cases — split into dedicated
  `tolerance_pct`/`acceptable_range_low`/`acceptable_range_high` columns so
  every `required_value` is now a plain scalar or empty.
- Removed a `schedule_critical` column that had leaked schedule-service's
  concern into the compliance gold set — a boundary the architecture is
  explicitly designed to keep separate.
- Added 7 boundary-value test rows (exact tolerance edges, one-unit-off
  failures) — the original 14 rows had exactly one exact-boundary case
  (`SWGR-LV-01`, 65==65) and zero coverage of the impedance tolerance band's
  actual edges, which is precisely where an off-by-one comparison bug hides.
- The propagation gold set's numeric values (previously only hand-verified
  once, after the earlier CPM float bug) were independently recomputed with
  a new script, `dataset/schedule/validate_propagation.py` — all 14 rows
  across both scenarios now match a from-scratch forward/backward pass.
- Caught mid-edit: a malformed CSV quote on the `ATS-01` row silently
  swallowed the first attempt at the 7 new boundary rows into one field —
  caught by re-parsing the file with `csv.reader` and checking row count,
  not by re-reading it visually.

All four dataset validators (`validate_cpm.py`, `validate_propagation.py`,
`check_dataset_integrity.py`, plus an ad-hoc schema-shape check) pass as of
this commit.
