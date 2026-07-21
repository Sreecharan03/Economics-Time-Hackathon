import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
import app.main as main_module
from app.main import app

client = TestClient(app)


def parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


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


# --- streaming endpoint ------------------------------------------------


def test_stream_emits_real_stage_events_then_complete(monkeypatch):
    async def fake_review(client, hint, text, spec_hint=None, on_stage=None):
        await on_stage({"stage": "reading", "status": "started"})
        await on_stage({"stage": "reading", "status": "done", "data": {"extracted_attributes": []}})
        await on_stage({"stage": "checking", "status": "started"})
        await on_stage({"stage": "checking", "status": "done", "data": {"overall_verdict": "PASS"}})
        return {
            "equipment_id": "XFMR-02", "extraction": {}, "compliance": {"overall_verdict": "PASS"},
            "schedule": None, "precedent": [], "draft_rfi": None,
            "requires_human_approval": True, "pipeline_warnings": [],
        }

    monkeypatch.setattr(main_module, "review_submittal", fake_review)
    resp = client.post("/review/submittal/stream", json={"equipment_id_hint": "XFMR-02", "raw_submittal_text": "text"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(resp.text)
    stages = [(e["stage"], e["status"]) for e in events]
    assert stages == [
        ("reading", "started"), ("reading", "done"),
        ("checking", "started"), ("checking", "done"),
        ("complete", "done"),
    ]
    assert events[-1]["data"]["equipment_id"] == "XFMR-02"


def test_stream_emits_failed_event_on_gateway_error(monkeypatch):
    async def failing_review(client, hint, text, spec_hint=None, on_stage=None):
        await on_stage({"stage": "reading", "status": "started"})
        from app.orchestrator import GatewayError
        raise GatewayError(503, "extraction-service unavailable: connection refused")

    monkeypatch.setattr(main_module, "review_submittal", failing_review)
    resp = client.post("/review/submittal/stream", json={"equipment_id_hint": "XFMR-01", "raw_submittal_text": "text"})
    assert resp.status_code == 200  # the HTTP response itself succeeds -- the error is an SSE event, not an HTTP error

    events = parse_sse(resp.text)
    assert events[0] == {"stage": "reading", "status": "started"}
    assert events[-1]["stage"] == "failed"
    assert events[-1]["status_code"] == 503
    assert "extraction-service unavailable" in events[-1]["detail"]


def test_stream_rejects_invalid_request_before_streaming():
    resp = client.post("/review/submittal/stream", json={"equipment_id_hint": "", "raw_submittal_text": "text"})
    assert resp.status_code == 422
