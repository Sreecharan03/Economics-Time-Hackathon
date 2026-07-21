import csv
from pathlib import Path

import pytest

GOLD_SET_PATH = (
    Path(__file__).parent.parent.parent.parent / "dataset" / "gold_set" / "rfi_retrieval_gold_set.csv"
)


def load_gold_set():
    with open(GOLD_SET_PATH, newline="") as f:
        return list(csv.DictReader(f))


GOLD_ROWS = load_gold_set()


def test_health_reports_indexed_count(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["indexed_rfis"] == 20  # all seed RFIs from dataset/rfis/rfis.json


@pytest.mark.parametrize("row", GOLD_ROWS, ids=[r["equipment_id"] + ":" + r["expected_rfi_id"] for r in GOLD_ROWS])
def test_hit_rate_at_3_against_gold_set(client, row):
    """The correct precedent must appear in the top 3 results -- this is the
    exact bar the README's own Test plan section sets."""
    resp = client.post("/retrieval/similar-rfis", json={"query_text": row["query_text"], "top_k": 3})
    assert resp.status_code == 200
    result_ids = [r["rfi_id"] for r in resp.json()["results"]]
    assert row["expected_rfi_id"] in result_ids, (
        f"expected {row['expected_rfi_id']} in top 3 for query {row['query_text']!r}, got {result_ids}"
    )


@pytest.mark.parametrize("row", GOLD_ROWS, ids=[r["equipment_id"] + ":" + r["expected_rfi_id"] for r in GOLD_ROWS])
def test_expected_precedent_ranks_first(client, row):
    """Stronger than hit-rate@3: for these seeded, unambiguous cases the
    correct precedent should be the single best match, not just top-3."""
    resp = client.post("/retrieval/similar-rfis", json={"query_text": row["query_text"], "top_k": 1})
    result_ids = [r["rfi_id"] for r in resp.json()["results"]]
    assert result_ids == [row["expected_rfi_id"]]


def test_results_sorted_descending_by_score(client):
    resp = client.post("/retrieval/similar-rfis", json={"query_text": "transformer impedance tolerance", "top_k": 10})
    scores = [r["score"] for r in resp.json()["results"]]
    assert scores == sorted(scores, reverse=True)


def test_top_k_limits_result_count(client):
    resp = client.post("/retrieval/similar-rfis", json={"query_text": "generator", "top_k": 2})
    assert len(resp.json()["results"]) == 2


def test_top_k_default_is_three(client):
    resp = client.post("/retrieval/similar-rfis", json={"query_text": "generator sizing"})
    assert len(resp.json()["results"]) == 3


def test_top_k_cannot_exceed_corpus_size_gracefully(client):
    resp = client.post("/retrieval/similar-rfis", json={"query_text": "generator", "top_k": 20})
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 20  # exactly the corpus size, no crash


@pytest.mark.parametrize("bad_top_k", [0, -1, 21, 1000])
def test_top_k_out_of_bounds_rejected(client, bad_top_k):
    resp = client.post("/retrieval/similar-rfis", json={"query_text": "generator", "top_k": bad_top_k})
    assert resp.status_code == 422


def test_empty_query_text_rejected(client):
    resp = client.post("/retrieval/similar-rfis", json={"query_text": "", "top_k": 3})
    assert resp.status_code == 422


def test_missing_query_text_rejected(client):
    resp = client.post("/retrieval/similar-rfis", json={"top_k": 3})
    assert resp.status_code == 422


def test_nonsense_query_still_returns_results_without_crashing(client):
    resp = client.post("/retrieval/similar-rfis", json={"query_text": "purple elephant banana spaceship", "top_k": 3})
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 3


def test_response_includes_all_contract_fields(client):
    resp = client.post("/retrieval/similar-rfis", json={"query_text": "transformer impedance", "top_k": 1})
    result = resp.json()["results"][0]
    for field in ("rfi_id", "source_project", "subject", "score", "resolution"):
        assert field in result


def test_score_is_within_cosine_similarity_bounds(client):
    resp = client.post("/retrieval/similar-rfis", json={"query_text": "transformer impedance", "top_k": 20})
    for r in resp.json()["results"]:
        assert -1.0001 <= r["score"] <= 1.0001
