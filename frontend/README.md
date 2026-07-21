# frontend

Next.js 16 / React 19 / TypeScript / Tailwind v4. Talks only to `gateway`
(`POST /review/submittal/stream`), never to the other five services
directly, per the top-level README's orchestration boundary.

## What it does

Four screens described in the original plan, all on one page as a
progressive reveal rather than separate routes (there's only one flow, no
navigation needed):

1. **Submittal input** — paste vendor spec text, or load one of four real
   examples from the project's own dataset (one for each possible outcome:
   deadline-critical fail, non-critical fail, spec-internal conflict, clean
   pass).
2. **Compliance result** — verdict, spec citation, submitted vs. required
   value. PASS/FAIL/CONFLICT are three different colors (green/red/violet),
   not the same red styled three ways — a CONFLICT is a spec contradicting
   itself, not a vendor mistake, and shouldn't look like one.
3. **Schedule impact** — a timeline distinguishing "CRITICAL, deadline
   moves" from "FLAGGED, N days of buffer remain," per
   `schedule-service/README.md`'s explicit warning that these are different
   urgency levels, not the same alert.
4. **Drafted RFI** — the draft text, its citations, and an Approve / Edit /
   Reject action. There is no send button and no backend persistence for
   the decision yet (`drafting-service`'s `drafted_rfi.approved` column
   exists but nothing writes to it) — approval is real UI state, honestly
   scoped as local-only, never an auto-send path.

## The live pipeline view

The right-hand sidebar shows five stages (plain names, not service names:
"Reading document," "Checking against spec," "Checking schedule impact,"
"Finding similar cases," "Drafting response") updating in real time via
Server-Sent Events as `gateway`'s `/review/submittal/stream` endpoint
actually executes each one — not a client-side animation timed to guess at
progress. `gateway/app/orchestrator.py`'s `on_stage` callback emits a real
event at every stage transition; the two BEST-EFFORT stages that run
concurrently (schedule + retrieval) visibly start together and finish
independently, because that's what's actually happening.

## Design

Deliberately not the default "AI product" blue-on-dark look: a warm
graphite base (not blue-tinted), a copper/amber accent as the interactive
color, and four distinct status hues (green/red/violet/amber) each meaning
exactly one thing. IBM Plex Sans + IBM Plex Mono instead of the
near-universal Inter/Geist pairing.

## Running it

```bash
npm install
npm run dev          # expects gateway reachable at NEXT_PUBLIC_GATEWAY_URL (default http://localhost:8000)
```

Or via the full stack: `docker compose -f infra/docker-compose.yml up -d --build frontend`
(brings up its `depends_on: [gateway]` chain too). `NEXT_PUBLIC_GATEWAY_URL`
is baked in at Docker build time (Next.js inlines `NEXT_PUBLIC_*` vars into
the client bundle at build, not read at container runtime) — see the `ARG`
in `Dockerfile` and the `build.args` in `infra/docker-compose.yml`.

## Not built

PDF upload (extraction-service has no PDF parsing path yet, text-paste
only); persisting the approve/reject decision anywhere; auth.
