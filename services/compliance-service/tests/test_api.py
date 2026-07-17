"""
End-to-end tests through the real FastAPI endpoint, which means through
spec_data.py's real load of equipment_master.json -- including its
conflicting_clauses data for ATS-01, which the flat gold-set CSV row can't
carry and test_engine.py's CSV-driven tests deliberately skip. This is where
CONFLICT gets full round-trip coverage.

Driven directly off dataset/submittals/equipment_master.json rather than a
second hand-typed fixture, for the same reason spec_data.py itself reads
that file: one source of truth, not a second copy that can drift.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[3]
with open(REPO_ROOT / "dataset" / "submittals" / "equipment_master.json") as f:
    _EQUIPMENT = json.load(f)["equipment"]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.parametrize("equip", _EQUIPMENT, ids=[e["equipment_id"] for e in _EQUIPMENT])
def test_all_12_equipment_items_end_to_end(equip):
    """Runs every real equipment item's actual submitted values through the
    live API and checks against equipment_master.json's own recorded
    verdicts -- this is the same cross-check check_dataset_integrity.py does
    statically, but now exercised through the actual service code path."""
    payload = {
        "equipment_id": equip["equipment_id"],
        "extracted_attributes": [
            {"attribute": a["attribute"], "value": a["submitted_value"], "unit": a["unit"]}
            for a in equip["attributes"]
        ],
    }
    r = client.post("/compliance/check", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["overall_verdict"] == equip["verdict"], (
        f"{equip['equipment_id']}: API returned overall_verdict={body['overall_verdict']!r} "
        f"but equipment_master.json says {equip['verdict']!r}"
    )
    assert len(body["results"]) == len(equip["attributes"])
    for result, expected_attr in zip(body["results"], equip["attributes"]):
        assert result["attribute"] == expected_attr["attribute"]
        assert result["verdict"] == expected_attr["verdict"], (
            f"{equip['equipment_id']}/{expected_attr['attribute']}: "
            f"API={result['verdict']} vs master={expected_attr['verdict']}"
        )


def test_ats01_conflict_includes_both_clauses_end_to_end():
    """The one CONFLICT case, specifically checking the conflicting_clauses
    payload round-trips correctly from equipment_master.json through
    spec_data.py through the engine through the API response."""
    r = client.post("/compliance/check", json={
        "equipment_id": "ATS-01",
        "extracted_attributes": [{"attribute": "transfer_time_cycles", "value": 4, "unit": "cycles"}],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["overall_verdict"] == "CONFLICT"
    clauses = body["results"][0]["conflicting_clauses"]
    assert clauses is not None
    clause_names = {c["clause"] for c in clauses}
    assert clause_names == {"26 36 00.2", "26 05 00 3.4.C"}


def test_ups01_dual_attribute_fail_rollup():
    """UPS-01 fails on two independent attributes -- overall_verdict must
    still be a single FAIL, and both individual results must be present and
    correctly labeled, not collapsed into one."""
    r = client.post("/compliance/check", json={
        "equipment_id": "UPS-01",
        "extracted_attributes": [
            {"attribute": "input_breaker_kAIC", "value": 65, "unit": "kAIC"},
            {"attribute": "battery_runtime_min", "value": 7, "unit": "minutes at 100% load"},
        ],
    })
    body = r.json()
    assert body["overall_verdict"] == "FAIL"
    assert len(body["results"]) == 2
    assert all(res["verdict"] == "FAIL" for res in body["results"])


# ---------------------------------------------------------------------------
# Error paths -- the API must fail loudly and specifically, never guess.
# ---------------------------------------------------------------------------

def test_unknown_equipment_id_returns_404():
    r = client.post("/compliance/check", json={
        "equipment_id": "NOT-A-REAL-EQUIPMENT-ID",
        "extracted_attributes": [{"attribute": "impedance_pct", "value": 5.0}],
    })
    assert r.status_code == 404


def test_unknown_attribute_for_known_equipment_returns_404():
    r = client.post("/compliance/check", json={
        "equipment_id": "XFMR-01",
        "extracted_attributes": [{"attribute": "not_a_real_attribute", "value": 5.0}],
    })
    assert r.status_code == 404


def test_malformed_numeric_value_returns_422():
    r = client.post("/compliance/check", json={
        "equipment_id": "XFMR-01",
        "extracted_attributes": [{"attribute": "impedance_pct", "value": "not-a-number"}],
    })
    assert r.status_code == 422


def test_unit_mismatch_returns_422():
    r = client.post("/compliance/check", json={
        "equipment_id": "XFMR-01",
        "extracted_attributes": [{"attribute": "impedance_pct", "value": 5.75, "unit": "kA"}],
    })
    assert r.status_code == 422


def test_empty_extracted_attributes_rejected_by_schema():
    r = client.post("/compliance/check", json={"equipment_id": "XFMR-01", "extracted_attributes": []})
    assert r.status_code == 422  # pydantic min_length=1 violation


def test_missing_equipment_id_rejected_by_schema():
    r = client.post("/compliance/check", json={"extracted_attributes": [{"attribute": "x", "value": 1}]})
    assert r.status_code == 422
