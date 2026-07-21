import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
import app.main as main_module
from app.main import app

client = TestClient(app)

VALID_PAYLOAD = {
    "equipment_id": "XFMR-01",
    "compliance_result": {
        "equipment_id": "XFMR-01",
        "overall_verdict": "FAIL",
        "results": [
            {
                "attribute": "impedance_pct",
                "submitted_value": 7.0,
                "required_value": 5.75,
                "unit": "%",
                "verdict": "FAIL",
                "spec_section": "26 12 00.3",
                "rationale": "exceeds tolerance",
            }
        ],
    },
    "schedule_result": {
        "triggering_activity": "SUBM-XFMR-01",
        "milestone_impact": {
            "activity_id": "CX-L5-IST",
            "activity_name": "IST",
            "slip_days": 14,
            "critical": True,
        },
        "urgency": "CRITICAL",
    },
    "precedent": [{"rfi_id": "RFI-HIST-003", "source_project": "Ashburn", "resolution": "..."}],
}


def test_health_reports_llm_configured_flag():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "llm_configured" in resp.json()


def test_drafting_without_configured_key_returns_501(monkeypatch):
    def raising_fn(req, llm_fn=None):
        from app.llm_client import LLMNotConfigured
        raise LLMNotConfigured("no key")

    monkeypatch.setattr(main_module, "draft_rfi", raising_fn)
    resp = client.post("/drafting/rfi", json=VALID_PAYLOAD)
    assert resp.status_code == 501


def test_drafting_missing_equipment_id_rejected():
    bad = {k: v for k, v in VALID_PAYLOAD.items() if k != "equipment_id"}
    resp = client.post("/drafting/rfi", json=bad)
    assert resp.status_code == 422


def test_drafting_missing_compliance_result_rejected():
    bad = {k: v for k, v in VALID_PAYLOAD.items() if k != "compliance_result"}
    resp = client.post("/drafting/rfi", json=bad)
    assert resp.status_code == 422


def test_drafting_without_schedule_result_accepted():
    payload = {**VALID_PAYLOAD, "schedule_result": None}
    resp = client.post("/drafting/rfi", json=payload)
    # will 501 without a key, but must NOT be a 422 -- schedule_result is optional
    assert resp.status_code in (200, 501, 502)


def test_drafting_without_precedent_defaults_to_empty_list():
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "precedent"}
    resp = client.post("/drafting/rfi", json=payload)
    assert resp.status_code in (200, 501, 502)


def test_drafting_happy_path_with_mocked_draft(monkeypatch):
    from app.models import Citation, DraftRfiBody

    def fake_draft(req, llm_fn=None):
        return DraftRfiBody(subject="s", body="b", citations=[Citation(type="spec_clause", ref="26 12 00.3")]), []

    monkeypatch.setattr(main_module, "draft_rfi", fake_draft)
    resp = client.post("/drafting/rfi", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["requires_human_approval"] is True
    assert body["draft_rfi"]["subject"] == "s"
    assert body["draft_warnings"] == []


def test_drafting_always_requires_human_approval_even_with_no_warnings(monkeypatch):
    from app.models import DraftRfiBody

    def fake_draft(req, llm_fn=None):
        return DraftRfiBody(subject="s", body="b", citations=[]), []

    monkeypatch.setattr(main_module, "draft_rfi", fake_draft)
    resp = client.post("/drafting/rfi", json=VALID_PAYLOAD)
    assert resp.json()["requires_human_approval"] is True


def test_drafting_malformed_llm_output_returns_502(monkeypatch):
    def raising_fn(req, llm_fn=None):
        from app.drafter import DraftingError
        raise DraftingError("bad json")

    monkeypatch.setattr(main_module, "draft_rfi", raising_fn)
    resp = client.post("/drafting/rfi", json=VALID_PAYLOAD)
    assert resp.status_code == 502


def test_drafting_response_matches_contract_shape(monkeypatch):
    from app.models import Citation, DraftRfiBody

    def fake_draft(req, llm_fn=None):
        return DraftRfiBody(subject="s", body="b", citations=[Citation(type="spec_clause", ref="26 12 00.3")]), ["a warning"]

    monkeypatch.setattr(main_module, "draft_rfi", fake_draft)
    resp = client.post("/drafting/rfi", json=VALID_PAYLOAD)
    body = resp.json()
    assert set(body.keys()) == {"draft_rfi", "requires_human_approval", "draft_warnings"}
    assert set(body["draft_rfi"].keys()) == {"subject", "body", "citations"}
    assert body["draft_warnings"] == ["a warning"]
