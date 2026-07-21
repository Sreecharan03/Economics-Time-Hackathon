import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
import app.main as main_module
from app.main import app

client = TestClient(app)


def test_health_reports_llm_configured_flag():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "llm_configured" in resp.json()


def test_extraction_without_configured_key_returns_501(monkeypatch):
    monkeypatch.setattr("app.llm_client.is_configured", lambda: False)

    def raising_fn(raw_text, hint, section):
        from app.llm_client import LLMNotConfigured
        raise LLMNotConfigured("no key")

    monkeypatch.setattr(main_module, "extract_from_text", lambda raw_text, hint, section: raising_fn(raw_text, hint, section))
    resp = client.post("/extraction/submittal", json={"raw_text": "some text"})
    assert resp.status_code == 501


def test_extraction_empty_raw_text_rejected():
    resp = client.post("/extraction/submittal", json={"raw_text": ""})
    assert resp.status_code == 422


def test_extraction_missing_raw_text_rejected():
    resp = client.post("/extraction/submittal", json={})
    assert resp.status_code == 422


def test_extraction_happy_path_with_mocked_llm(monkeypatch):
    def fake_extract(raw_text, equipment_id_hint=None, spec_section_hint=None, llm_fn=None):
        from app.extractor import ExtractedAttribute
        return (
            equipment_id_hint,
            [ExtractedAttribute(attribute="impedance_pct", value=7.0, unit="%", source_span="quote", confidence=0.95)],
            [],
        )

    monkeypatch.setattr(main_module, "extract_from_text", fake_extract)
    resp = client.post(
        "/extraction/submittal",
        json={"equipment_id_hint": "XFMR-01", "raw_text": "Impedance 7.0%", "spec_section_hint": "26 12 00"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["equipment_id"] == "XFMR-01"
    assert body["extracted_attributes"][0]["attribute"] == "impedance_pct"
    assert body["extraction_warnings"] == []


def test_extraction_malformed_llm_output_returns_502(monkeypatch):
    def raising_extract(raw_text, equipment_id_hint=None, spec_section_hint=None, llm_fn=None):
        from app.extractor import ExtractionError
        raise ExtractionError("bad json")

    monkeypatch.setattr(main_module, "extract_from_text", raising_extract)
    resp = client.post("/extraction/submittal", json={"raw_text": "some text"})
    assert resp.status_code == 502


def test_extraction_response_matches_contract_shape(monkeypatch):
    def fake_extract(raw_text, equipment_id_hint=None, spec_section_hint=None, llm_fn=None):
        from app.extractor import ExtractedAttribute
        return (
            "XFMR-01",
            [ExtractedAttribute(attribute="impedance_pct", value=7.0, unit="%", source_span="q", confidence=0.95)],
            ["a warning"],
        )

    monkeypatch.setattr(main_module, "extract_from_text", fake_extract)
    resp = client.post("/extraction/submittal", json={"raw_text": "x"})
    body = resp.json()
    assert set(body.keys()) == {"equipment_id", "extracted_attributes", "extraction_warnings"}
    attr = body["extracted_attributes"][0]
    assert set(attr.keys()) == {"attribute", "value", "unit", "source_span", "confidence"}
