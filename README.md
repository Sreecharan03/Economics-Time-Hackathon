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

**Overall: `[████████████████░░░░]` ~82%**

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
| `gateway` | 12% | ✅ Orchestration + 3 real cross-service bugs found & fixed + tests + Docker, verified end-to-end | `[███████████████░░░░░]` 80% |
| `frontend` | 8% | ✅ All 4 verdict states verified in a real browser + Docker, live SSE pipeline view | `[█████████████████░░░]` 85% |
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

### `gateway` (2026-07-21)

Sixth service implemented -- orchestrates the other five behind one HTTP
surface (`POST /review/submittal`), per the order in this service's own
README: extraction -> compliance -> (if FAIL/CONFLICT) schedule + retrieval
in parallel -> drafting. Contains no domain logic of its own; the real
design decision is REQUIRED vs BEST-EFFORT -- extraction and compliance
failures abort the whole request (`GatewayError`, 502/503), but
schedule/retrieval/drafting failures degrade gracefully (null/empty field +
a `pipeline_warnings` entry) since a compliance verdict is still useful on
its own even if, say, drafting-service is down.

Filled a second dataset gap on the way: 7 of the 12 equipment items had no
raw submittal text (`raw_submittal_file: null`), which blocks the gateway's
own stated test plan ("all 12 equipment items ... against a docker-compose
stack of all six services"). Added realistic `.txt` submittals for
XFMR-02, SWGR-LV-01, GEN-01, GEN-02, CRAC-02, PDU-01, and ATS-01, matching
the values already fixed in the gold set, so the full-pipeline test is
genuine across the entire dataset, not five of twelve items.

**Three real cross-service integration bugs, found only because this
service actually chains the other five together instead of testing each in
isolation** (see `app/spec_filter.py`'s docstring for the full detail):

1. *Coverage mismatch*: extraction-service pulls every spec value off a
   datasheet (17 for XFMR-01); compliance-service 404s on the first
   attribute name it doesn't track for that equipment. Fixed by filtering
   to only checkable attributes before forwarding, using the same
   `equipment_master.json` both services already read -- not a third
   hand-typed vocabulary.
2. *Unit label mismatch*: compliance-service's engine refuses to compare
   values whose unit string doesn't match the spec's exactly (`"kW"` vs
   `"kW standby"` 502'd the real GEN-01/GEN-02 pipeline on first live run,
   caught by the live test, not a mock). Fixed by substituting the
   canonical spec unit before forwarding.
3. *ENUM split mismatch*: extraction-service's `units.py` correctly splits
   `"7.0%"` into `value=7.0, unit="%"` for RANGE attributes, but the same
   logic also splits `"480V"` into `value=480, unit="V"` for the ENUM-
   checked `input_voltage` attribute, which then fails an exact string
   match against `"480V"` (real bug: PDU-01 came back FAIL against a PASS
   gold label). Fixed by recombining value+unit for attributes
   `equipment_master.json`'s own shape identifies as ENUM (no
   `acceptable_range_low`/`high`), not by changing either service's
   already-tested internal logic.

A fourth issue was a dataset-authoring mistake, not a service bug: the
synthetic GEN-02 submittal text I wrote referenced GEN-01's and the spec
minimum's kW values in the same sentence as GEN-02's own rating, and the
LLM (reasonably) extracted all three as three readings of the same
attribute, dragging a real PASS to FAIL via an unrelated number. Fixed the
source text, and separately hardened `spec_filter.py` to keep only the
highest-confidence entry whenever extraction returns more than one value
for the same attribute name -- a real submittal could plausibly have this
ambiguity even with cleaner prose.

Also fixed weak precedent retrieval: compliance-service's rationale text is
deliberately generic ("Submitted 7.0 is outside acceptable range [5.32,
6.18]."), with no domain words in it -- on first live run this alone pulled
RFI-HIST-001 (a UPS breaker RFI) for a transformer-impedance deviation
instead of the actually-relevant RFI-HIST-003. Fixed by prepending the
equipment's description and attribute name to the retrieval query, both
already available without another service call.

Test suite: 48 pytest nodes -- 24 in `test_orchestrator.py` (mocked via
`httpx.MockTransport`, covering every REQUIRED-vs-BEST-EFFORT failure mode
per service, the coverage/unit/ENUM/dedup fixes above, PASS/FAIL/CONFLICT
branching, and the `requires_human_approval` invariant), 7 in `test_api.py`
(request validation), and 17 in `test_live_full_pipeline.py` -- the
README's own stated test plan: all 12 equipment items run through the real
6-service Docker Compose stack, checked against `equipment_master.json`'s
gold verdict, plus dedicated checks for both hero scenarios (XFMR-01
CRITICAL, SWGR-MV-01 FLAGGED) and the ATS-01 CONFLICT case. All 48 pass
against the fully containerized stack, not just a local dev run.

### `frontend` (2026-07-21)

Seventh piece, and the last 0% row. Next.js 16 / React 19 / TypeScript /
Tailwind v4, talking only to `gateway` per the orchestration boundary.
Deliberately not the default "AI product" look -- a warm graphite base
instead of the near-universal blue-tinted dark theme, copper/amber as the
interactive accent, and four distinct status hues (PASS green / FAIL red /
CONFLICT violet / FLAGGED amber) so a spec-internal contradiction never
reads as the same alert as a vendor's mistake, per the frontend spec's
explicit warning about exactly that.

The pipeline sidebar is real, not decorative: `gateway/app/main.py` gained
a `POST /review/submittal/stream` SSE endpoint, and `orchestrator.py`
gained an optional `on_stage` callback (default no-op, so all 48 existing
gateway tests needed zero changes) that fires at every real stage
transition. The frontend consumes that stream and updates five plain-
language stages ("Reading document," "Checking against spec," "Checking
schedule impact," "Finding similar cases," "Drafting response") live --
including showing the two BEST-EFFORT stages (schedule + retrieval)
visibly starting together and finishing independently, because that's what
the orchestrator actually does, not a client-side animation timed to guess
at it.

Verified in an actual headless browser (no `chromium-cli` available in
this environment; installed the `playwright` npm package and drove it
directly), not just `next build` succeeding: all four possible verdict
outcomes exercised end-to-end against the full seven-container Docker
Compose stack (critical FAIL, non-critical FAIL, CONFLICT, and PASS),
screenshotted at each stage, zero browser console errors, every number on
screen cross-checked against the real API response (the schedule timeline
showing day 745 -> day 759 is the actual CPM output, not a mock). The
Approve button flips real local UI state; per the frontend spec, there is
no send action and no persistence of that decision yet, honestly scoped
that way rather than faked.

Not built: PDF upload (extraction-service has no PDF parsing path yet),
persisting the approve/reject decision (`drafted_rfi.approved` exists in
the schema, nothing writes to it), auth.

### Real deployment bug: same-origin proxy (2026-07-21)

Found only by actually deploying to a cloud sandbox and clicking through it
from a real external browser, not by any local test: the frontend was
calling `gateway` at its own public URL directly from browser JS. That
works fine when both are on `localhost`, but breaks the moment the two are
on different machines from the browser's point of view -- which is exactly
what happens in a cloud studio environment, where typically only *one*
port ends up publicly exposed. The browser's request to gateway's port
never even reached the container; it dead-ended at the sandbox's edge
proxy, surfacing as a CORS error with no useful signal about the real
cause.

Fixed by adding `app/api/gateway/[...path]/route.ts` -- a Next.js Route
Handler that proxies same-origin, forwarding to `gateway` over the private
Docker network (`http://gateway:8000`) from the server side, streaming the
SSE response straight through rather than buffering it. The browser now
only ever talks to the frontend's own origin. This is a strictly better
architecture regardless of environment (one less CORS surface, one less
public port needed generally), not just a workaround for this sandbox --
kept it after moving off the temporary `NEXT_PUBLIC_GATEWAY_URL` /
`FRONTEND_ORIGIN` build-time approach entirely.

### What's left

Every one of the six services plus the frontend has now been proven
against the real dataset over real HTTP or in a real browser, not
simulated -- five genuine integration bugs were found and fixed across the
gateway and frontend work specifically because those two only surface once
independently-tested pieces are actually chained together. What remains is
final integration/demo polish (the 5% row still at 0%), not further
de-risking of any individual piece.

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
