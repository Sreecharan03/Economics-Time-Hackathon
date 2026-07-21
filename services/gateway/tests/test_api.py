import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
import app.main as main_module
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_missing_raw_submittal_text_rejected():
    resp = client.post("/review/submittal", json={"equipment_id_hint": "XFMR-01"})
    assert resp.status_code == 422


def test_empty_raw_submittal_text_rejected():
    resp = client.post("/review/submittal", json={"equipment_id_hint": "XFMR-01", "raw_submittal_text": ""})
    assert resp.status_code == 422


def test_missing_equipment_id_hint_rejected():
    resp = client.post("/review/submittal", json={"raw_submittal_text": "some text"})
    assert resp.status_code == 422


def test_empty_equipment_id_hint_rejected():
    resp = client.post("/review/submittal", json={"equipment_id_hint": "", "raw_submittal_text": "some text"})
    assert resp.status_code == 422


def test_gateway_error_propagates_as_http_exception(monkeypatch):
    async def raising_review(client, hint, text, spec_hint=None):
        from app.orchestrator import GatewayError
        raise GatewayError(503, "extraction-service unavailable: connection refused")

    monkeypatch.setattr(main_module, "review_submittal", raising_review)
    resp = client.post("/review/submittal", json={"equipment_id_hint": "XFMR-01", "raw_submittal_text": "text"})
    assert resp.status_code == 503
    assert "extraction-service unavailable" in resp.json()["detail"]


def test_successful_review_matches_response_contract(monkeypatch):
    async def fake_review(client, hint, text, spec_hint=None):
        return {
            "equipment_id": "XFMR-01",
            "extraction": {"equipment_id": "XFMR-01", "extracted_attributes": [], "extraction_warnings": []},
            "compliance": None,
            "schedule": None,
            "precedent": [],
            "draft_rfi": None,
            "requires_human_approval": True,
            "pipeline_warnings": ["no attributes extracted"],
        }

    monkeypatch.setattr(main_module, "review_submittal", fake_review)
    resp = client.post("/review/submittal", json={"equipment_id_hint": "XFMR-01", "raw_submittal_text": "text"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "equipment_id", "extraction", "compliance", "schedule", "precedent", "draft_rfi",
        "requires_human_approval", "pipeline_warnings",
    }
