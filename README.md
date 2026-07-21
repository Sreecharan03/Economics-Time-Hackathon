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

**Overall: `[█████████████░░░░░░░]` ~66%**

Weighted by remaining effort, not file count — Phase 0 was real work (dataset
+ validation + architecture) but implementation/testing across 6 services,
the frontend, and integration is the bulk of what's left.

| Component | Weight | Status | Progress |
|---|---|---|---|
| Phase 0 — design, dataset, scaffold | 15% | ✅ Complete | `[████████████████████]` 100% |
| `compliance-service` | 12% | ✅ Engine + API + tests + Docker, verified end-to-end | `[██████████████████░░]` 90% |
| `schedule-service` | 12% | ✅ Engine + API + tests + Docker, verified end-to-end | `[██████████████████░░]` 90% |
| `extraction-service` | 12% | ✅ Groq extraction + verified source-spans + API + tests + Docker, verified end-to-end | `[████████████████░░░░]` 80% |
| `retrieval-service` | 12% | ✅ Embeddings + pgvector + API + tests + Docker, verified end-to-end | `[█████████████████░░░]` 85% |
| `drafting-service` | 12% | ✅ Groq drafting + citation validation + API + tests + Docker, verified end-to-end incl. full cross-service chain | `[████████████████░░░░]` 80% |
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

### `retrieval-service` (2026-07-21)

Third service implemented, and the first to actually use Postgres at request
time (`compliance-service`/`schedule-service` both read their seed files
directly, by design, per their own README notes). `embeddings.py` wraps a
local `sentence-transformers` model (`all-MiniLM-L6-v2`, 384-dim, no external
API — Groq has no embeddings endpoint) and is the only place index-time and
query-time text formatting can diverge, so both `seed_rfis.py` and
`main.py` call the same `rfi_index_text()` helper rather than each building
their own string. `main.py` does one thing: embed the query, run a pgvector
cosine search, shape the response — no ranking logic beyond what the SQL
`ORDER BY embedding <=> :vec` already does.

Filled a gap the service's own README flagged as a tracked follow-up: wrote
`dataset/gold_set/rfi_retrieval_gold_set.csv`, mapping each of the 5 seeded
deviations named in the README (plus a 6th, GEN-01, added for extra hit-rate
coverage) to its known-relevant precedent RFI.

Test suite: 35 pytest nodes (7 in `test_embeddings.py`, 28 in `test_api.py`),
covering every gold-set row at both hit-rate@3 (README's stated bar) and the
stronger rank-1 exact match, `top_k` boundary validation, empty/missing-field
rejection, score-ordering and score-bounds sanity, and a nonsense-query
smoke test.

Verified beyond pytest: built as a real Docker image, run as a container
alongside `postgres` via `docker compose up`, seeded through the real
`seed_rfis.py` running inside the container against the containerized DB,
then hit over real HTTP — `RFI-HIST-003` (the exact precedent case) came
back for the transformer-impedance query at 0.763 cosine similarity vs. 0.343
for the next-best match, a real semantic margin, not a coincidence of the
tiny corpus.

One real bug caught in that process, not by pytest but by actually querying
the running service twice with different `top_k` values and noticing the
result count didn't match: the `rfi_embedding` table's `ivfflat` index was
built with `lists = 20` for a corpus that currently *has* 20 rows. pgvector's
default `ivfflat.probes = 1` means only ~1/20th of the corpus gets searched
per query at that list count — queries were silently dropping relevant
results, including the gold-set precedents, well before any test caught it
(the first test run had 14 of 35 nodes failing on exactly this). Fixed with
`SET LOCAL ivfflat.probes = 20` per request in `main.py`, forcing
exhaustive-equivalent search; flagged in a code comment to revisit once the
corpus is large enough that lists/probes should scale with row count instead
of being pinned to "search everything."

Not yet done: `extraction-service` and `drafting-service` (both need
`GROQ_API_KEY`, the one piece of external configuration this project depends
on) and `gateway` to orchestrate all three real services plus the two
LLM-backed ones behind a single HTTP surface for the frontend.

### `extraction-service` (2026-07-21)

Fourth service implemented -- the first (and, by design, only) service that
calls an LLM to do real interpretive work rather than compose already-decided
facts (that's `drafting-service`'s narrower job). Groq access came online
this session (`GROQ_API_KEY` now set in `infra/.env`, gitignored, never
committed). `llm_client.py` is a thin wrapper (model: `llama-3.3-70b-versatile`)
kept deliberately separate from `extractor.py` so the LLM call is injectable
in tests. `units.py` handles the common real failure mode of the model
embedding a unit inside the value string (`"7.0%"` instead of `value: 7.0,
unit: "%"`) despite being told not to -- plain Python, not a second model
call, per the project's extraction-vs-judgment split.

The actual anti-hallucination mechanism is deterministic, not the model's
self-reported confidence: every `source_span` the model returns is checked
as a real substring of the input text (`verify_source_span`), whitespace-
normalized, with a fuzzy case-insensitive fallback -- confidence (0.95 /
0.7 / 0.3) is derived from that check, not asked of the model.

Test suite: 57 pytest nodes (19 in `test_units.py`, 24 in `test_extractor.py`,
7 in `test_api.py`), covering JSON-fence stripping, malformed-output
rejection, missing-field skip-not-crash behavior, hallucinated-span
detection, and the full mocked-LLM pipeline -- all fast and free (injected
fake `llm_fn`, no network). Separately, `test_live_groq.py` (7 more nodes,
skipped automatically without `GROQ_API_KEY`) runs the real pipeline against
all 5 actual `dataset/submittals/*.txt` files and asserts 100% recall against
the known submitted values, per this service's own README test plan
(target >=0.90) -- all 7 passed on the first real run, including the
dual-attribute UPS-01/UPS-02 cases.

Verified beyond pytest: built as a real Docker image, run as a container
with `GROQ_API_KEY` passed through `docker compose`, hit over real HTTP
against the actual XFMR-01 submittal text -- extracted all 17 spec values
present in the document (not just the one the gold set tracks), every
`source_span` an exact verbatim match (confidence 0.95, zero warnings),
including the impedance value that drives the hero compliance scenario.

Not yet done: table extraction (README's pipeline step 2 -- no submittal in
the current dataset has a multi-row table, so this hasn't been exercised;
flagged, not silently skipped) and entity-resolution suggestions (explicitly
out of scope per README, needs a human-confirm UI step that doesn't exist
yet).

### `drafting-service` (2026-07-21)

Fifth service implemented -- the last of the three originally-scoped-but-
unbuilt services from this session's starting point. Takes already-decided
facts from `compliance-service`/`schedule-service`/`retrieval-service` as
input and composes prose; it does not judge, compute, or search anything
itself (see README's "what it does NOT do"). `requires_human_approval` is
hardcoded `True` in `main.py`, not a model-decided field -- no draft can
waive the human sign-off gate regardless of what the LLM returns.

The real guardrail is `validate_citations`: every citation the model claims
is checked against a `collect_valid_refs()` set built directly from the
request payload (spec_section strings from `compliance_result`, the
equipment_id, schedule activity_ids from `schedule_result`, rfi_ids from
`precedent`) -- a citation pointing anywhere else is dropped and surfaced in
`draft_warnings`, never silently kept. This is exactly the structural test
the service's own README specifies ("a unit test asserts this structurally
... rather than trying to grade prose quality").

Test suite: 38 pytest nodes (25 in `test_drafter.py`, 13 in `test_api.py`)
against an injected fake `llm_fn`, covering fence-stripped/malformed JSON,
missing-key rejection, citation validation (valid/dropped/wrong-type/
missing-field/mixed cases), and the optional `schedule_result`/`precedent`
paths. Separately, `test_live_groq.py` (4 more nodes, skipped without
`GROQ_API_KEY` or without the three upstream services reachable) does not
just call Groq in isolation -- it calls the *real* `compliance-service`,
`schedule-service`, and `retrieval-service` containers over HTTP to build
the request, then drafts against real Groq, for both the XFMR-01 (CRITICAL)
and SWGR-MV-01 (FLAGGED) scenarios. All 4 passed on the first real run,
zero dropped citations.

Verified beyond pytest: all four real services (`compliance-service`,
`schedule-service`, `retrieval-service`, `drafting-service`) built as Docker
images, brought up together via `docker compose`, and chained over real
HTTP end-to-end -- the exact "spec deviation -> schedule impact -> cited
RFI" narrative the source evaluation names as the project's only real
differentiation, now running as actual services talking to each other, not
a single script simulating the chain. Draft output for XFMR-01: cites
`26 12 00.3`, states the 14-day IST slip, references `RFI-HIST-003` by name
with its actual resolution, and closes with the required human-sign-off
language -- all three citations independently verified to resolve to real
payload fields.

Not yet done: persisting drafts to the `drafted_rfi` table (currently
stateless request/response, no `DATABASE_URL`) and the `approved` boolean
workflow that table already has a column for.

### What's left

`gateway` (orchestrate all five real services behind one HTTP surface) and
`frontend` (the only thing currently making this invisible to anyone who
isn't hitting the APIs directly) are the two remaining 0% rows, plus final
integration/demo polish. Every service that touches an LLM or a vector
search has now been proven against the real dataset over real HTTP, not
simulated -- what's left is orchestration and a UI, not further de-risking.

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
