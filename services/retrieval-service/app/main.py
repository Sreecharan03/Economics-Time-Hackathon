"""
FastAPI wrapper around pgvector similarity search. No LLM call, no drafting
logic -- this service only ranks precedent RFIs (see README.md's "what it
does NOT do"). Embedding a query is the only per-request compute cost; it's
a local sentence-transformers forward pass, no network call.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.embeddings import embed_text
from app.models import RfiMatch, SimilarRfisRequest, SimilarRfisResponse

app = FastAPI(title="retrieval-service")


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    count = session.execute(text("SELECT count(*) FROM rfi_embedding")).scalar()
    return {"status": "ok", "indexed_rfis": count}


@app.post("/retrieval/similar-rfis", response_model=SimilarRfisResponse)
def similar_rfis(req: SimilarRfisRequest, session: Session = Depends(get_session)) -> SimilarRfisResponse:
    vec = embed_text(req.query_text)
    # The ivfflat index (infra/db/migrations/001_initial_schema.sql) was built
    # with lists=20 for a corpus that currently HAS 20 rows -- with the
    # pgvector default of ivfflat.probes=1, that means ~1/20th of the corpus
    # gets searched per query, silently dropping relevant results. Force
    # exhaustive-equivalent search by probing every list; revisit once the
    # corpus is large enough that lists/probes should scale with row count
    # instead of being pinned to "all of them".
    session.execute(text("SET LOCAL ivfflat.probes = 20"))
    rows = session.execute(
        text(
            """
            SELECT r.rfi_id, r.source_project, r.subject, r.resolution,
                   1 - (e.embedding <=> :vec) AS score
            FROM rfi_embedding e
            JOIN rfi r ON r.rfi_id = e.rfi_id
            ORDER BY e.embedding <=> :vec
            LIMIT :k
            """
        ),
        {"vec": str(vec), "k": req.top_k},
    ).mappings().all()

    return SimilarRfisResponse(
        results=[
            RfiMatch(
                rfi_id=r["rfi_id"],
                source_project=r["source_project"],
                subject=r["subject"],
                score=round(float(r["score"]), 4),
                resolution=r["resolution"],
            )
            for r in rows
        ]
    )
