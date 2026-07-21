"""
Local, free, offline-capable embeddings for RFI retrieval. Deliberately not
routed through Groq -- Groq has no embeddings endpoint (see README.md).
all-MiniLM-L6-v2 is small (~80MB), CPU-friendly, and 384-dim, matching the
rfi_embedding.embedding column in infra/db/migrations/001_initial_schema.sql.
"""
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_text(text: str) -> list[float]:
    return get_model().encode(text, normalize_embeddings=True).tolist()


def rfi_index_text(rfi: dict) -> str:
    """Same text shape used both at seed time and at query time matters --
    if these diverge, cosine similarity degrades silently. Centralized here
    so seed_rfis.py and the query path can't drift apart."""
    return f"{rfi['subject']}. {rfi['question']} Tags: {', '.join(rfi.get('tags', []))}"
