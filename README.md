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

**Overall: `[███░░░░░░░░░░░░░░░░░]` 15%**

Weighted by remaining effort, not file count — Phase 0 was real work (dataset
+ validation + architecture) but implementation/testing across 6 services,
the frontend, and integration is the bulk of what's left.

| Component | Weight | Status | Progress |
|---|---|---|---|
| Phase 0 — design, dataset, scaffold | 15% | ✅ Complete | `[████████████████████]` 100% |
| `compliance-service` | 12% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| `schedule-service` | 12% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| `extraction-service` | 12% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| `retrieval-service` | 12% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| `drafting-service` | 12% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| `gateway` | 12% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| `frontend` | 8% | ⬜ Contract documented, no code | `[░░░░░░░░░░░░░░░░░░░░]` 0% |
| Integration + demo polish | 5% | ⬜ Not started | `[░░░░░░░░░░░░░░░░░░░░]` 0% |

**What "done" means for a service** (see [Push/test policy](#pushtest-policy)
below): not just code that runs, but a green pytest suite with deep edge-case
coverage. A service only moves out of "no code" once that bar is cleared.

### Push/test policy

Code changes to any `services/*/app/` push to GitHub only after that
service's `tests/` suite (target: ~1000+ distinct parametrized edge cases —
boundary values, malformed/missing input, unit mismatches, not just the
golden-path gold-set rows) is written and passing. This is a per-service bar,
not a whole-project one. Docs-only changes (this README, service READMEs)
are exempt and push freely. Local commits are never gated — only `git push`.

This table is updated every push, reflecting real state, not aspiration.
Last updated: 2026-07-17 (Phase 0 commit `b74cc57`, not yet pushed).
