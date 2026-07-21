import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.embeddings import EMBEDDING_DIM, embed_text, rfi_index_text


def test_embedding_dimension_matches_schema():
    vec = embed_text("transformer impedance out of tolerance")
    assert len(vec) == EMBEDDING_DIM == 384


def test_embedding_is_normalized():
    vec = embed_text("switchgear short circuit withstand rating")
    norm = math.sqrt(sum(x * x for x in vec))
    assert abs(norm - 1.0) < 1e-4


def test_embedding_deterministic_for_same_input():
    text = "UPS battery runtime shortfall"
    assert embed_text(text) == embed_text(text)


def test_embedding_differs_for_different_input():
    a = embed_text("transformer impedance deviation")
    b = embed_text("unrelated fire suppression clean agent substitution")
    # cosine similarity between unrelated texts should not be ~1
    dot = sum(x * y for x, y in zip(a, b))
    assert dot < 0.9


def test_embedding_similar_for_related_input():
    a = embed_text("transformer impedance outside tolerance band")
    b = embed_text("dry-type transformer impedance exceeds coordination study tolerance")
    dot = sum(x * y for x, y in zip(a, b))
    assert dot > 0.5  # related phrasing should score meaningfully higher than the unrelated pair above


def test_rfi_index_text_includes_subject_question_and_tags():
    rfi = {
        "subject": "Subj",
        "question": "Quest?",
        "tags": ["a", "b"],
    }
    text = rfi_index_text(rfi)
    assert "Subj" in text
    assert "Quest?" in text
    assert "a" in text and "b" in text


def test_rfi_index_text_handles_missing_tags():
    rfi = {"subject": "Subj", "question": "Quest?"}
    text = rfi_index_text(rfi)  # should not raise
    assert "Subj" in text
