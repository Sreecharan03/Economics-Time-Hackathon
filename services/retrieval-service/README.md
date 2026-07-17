# retrieval-service

## Responsibility

Given a detected deviation, find the most similar precedent RFIs from
`dataset/rfis/rfis.json` (20 synthetic historical RFIs across 5 fictional past
projects) so `drafting-service` can ground its draft in real precedent rather
than generating from nothing. Embeddings are computed with a local
`sentence-transformers` model (`all-MiniLM-L6-v2`) — not Groq, which has no
embeddings endpoint — so this service has no external API dependency at
request time beyond the local Postgres/pgvector instance.

## What it does NOT do

- Does not draft anything (`drafting-service`'s job). This service returns
  ranked precedent records, not text.
- Is not a general document chatbot. The only query shape it accepts is "find
  RFIs similar to this deviation," not open-ended Q&A over the RFI corpus.

## API contract

### `POST /retrieval/similar-rfis`

Request:
```json
{
  "query_text": "Transformer impedance 7.0% submitted, spec requires 5.75% +/-7.5% tolerance, invalidates protective coordination study",
  "top_k": 3
}
```

Response:
```json
{
  "results": [
    {
      "rfi_id": "RFI-HIST-003",
      "source_project": "Ashburn Campus Building 4",
      "subject": "Dry-type transformer impedance outside coordination study tolerance",
      "score": 0.89,
      "resolution": "EOR confirmed 7% falls outside the +/-7.5% tolerance band on 5.75% nominal (5.32-6.18% acceptable). Required custom low-impedance wind..."
    }
  ]
}
```

## Data dependency

Embeds all 20 RFIs from `dataset/rfis/rfis.json` into a `rfi_embedding` table
(`pgvector`) at seed time — this is a one-time indexing job, not something
computed per request. Per-request cost is one embedding call (local model,
no network) plus one pgvector similarity query.

## Test plan

Retrieval hit-rate@3 against a hand-labeled mapping of each seeded deviation
(`XFMR-01`, `SWGR-MV-01`, `UPS-01`, `CRAC-01`, `ATS-01`) to its known-relevant
RFI (`RFI-HIST-003`, `RFI-HIST-005`, `RFI-HIST-001`/`RFI-HIST-002`,
`RFI-HIST-004`, `RFI-HIST-007` respectively) — the correct precedent must
appear in the top 3 results for every seeded case. This mapping needs to be
written as an explicit gold file in `dataset/gold_set/` before this service's
tests can run (not yet created — tracked as follow-up).
