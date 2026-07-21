"""
The test README.md actually specifies: run the full pipeline end-to-end for
all 12 equipment items in dataset/submittals/equipment_master.json against a
docker-compose stack of all six services, and assert the final assembled
result matches the gold sets. This is the test that proves the
"compliance -> schedule -> commissioning" chain works end-to-end, not just
that each service passes its own unit tests in isolation.

Requires GATEWAY_URL (default localhost:8000) plus all five downstream
services reachable, and GROQ_API_KEY set (extraction/drafting need it).
Skipped automatically if the gateway isn't reachable.
"""
import json
import os
from pathlib import Path

import httpx
import pytest

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000")
DATASET_DIR = Path(__file__).parent.parent.parent.parent / "dataset"


def _gateway_reachable() -> bool:
    try:
        httpx.get(f"{GATEWAY_URL}/health", timeout=3.0).raise_for_status()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gateway_reachable(), reason=f"gateway not reachable at {GATEWAY_URL}")

EQUIPMENT = json.loads((DATASET_DIR / "submittals" / "equipment_master.json").read_text())["equipment"]


def review(equipment_id: str, raw_text: str, spec_section: str | None = None) -> dict:
    resp = httpx.post(
        f"{GATEWAY_URL}/review/submittal",
        json={"equipment_id_hint": equipment_id, "raw_submittal_text": raw_text, "spec_section_hint": spec_section},
        timeout=30.0,
    )
    assert resp.status_code == 200, f"{equipment_id}: gateway returned {resp.status_code}: {resp.text}"
    return resp.json()


@pytest.mark.parametrize("item", EQUIPMENT, ids=[e["equipment_id"] for e in EQUIPMENT])
def test_live_full_pipeline_matches_gold_verdict_for_all_12_items(item):
    """dataset/submittals/equipment_master.json's own `verdict` field is the
    gold rollup (independently checked against compliance_gold_set.csv by
    dataset/validate_cpm.py during the gold-set audit) -- this is the same
    ground truth, exercised through the real 6-service chain instead of a
    file read."""
    raw_text = (DATASET_DIR / "submittals" / item["raw_submittal_file"]).read_text()
    body = review(item["equipment_id"], raw_text, item["spec_section"])

    assert body["equipment_id"] == item["equipment_id"]
    assert body["compliance"] is not None, f"pipeline_warnings: {body['pipeline_warnings']}"
    assert body["compliance"]["overall_verdict"] == item["verdict"]
    assert body["requires_human_approval"] is True

    if item["verdict"] == "PASS":
        assert body["schedule"] is None
        assert body["precedent"] == []
        assert body["draft_rfi"] is None
    else:
        assert body["draft_rfi"] is not None, f"{item['equipment_id']}: expected a draft RFI for a {item['verdict']} verdict"
        assert body["draft_rfi"]["citations"], f"{item['equipment_id']}: draft had zero citations"


def test_live_xfmr01_hero_scenario_end_to_end():
    """The scenario the whole demo narrative is built around: transformer
    impedance -> critical path -> 14-day IST slip -> cited precedent."""
    item = next(e for e in EQUIPMENT if e["equipment_id"] == "XFMR-01")
    raw_text = (DATASET_DIR / "submittals" / item["raw_submittal_file"]).read_text()
    body = review("XFMR-01", raw_text, item["spec_section"])

    assert body["compliance"]["overall_verdict"] == "FAIL"
    assert body["schedule"]["urgency"] == "CRITICAL"
    assert body["schedule"]["milestone_impact"]["slip_days"] == 14
    assert body["schedule"]["milestone_impact"]["activity_id"] == "CX-L5-IST"
    assert body["precedent"][0]["rfi_id"] == "RFI-HIST-003"
    citation_refs = [c["ref"] for c in body["draft_rfi"]["citations"]]
    assert "26 12 00.3" in citation_refs


def test_live_swgr01_flagged_not_critical_scenario_end_to_end():
    """The 'don't cry wolf' scenario: a real deviation that the CPM engine
    correctly determines does NOT threaten the commissioning date."""
    item = next(e for e in EQUIPMENT if e["equipment_id"] == "SWGR-MV-01")
    raw_text = (DATASET_DIR / "submittals" / item["raw_submittal_file"]).read_text()
    body = review("SWGR-MV-01", raw_text, item["spec_section"])

    assert body["compliance"]["overall_verdict"] == "FAIL"
    assert body["schedule"]["urgency"] == "FLAGGED"
    assert body["schedule"]["milestone_impact"]["slip_days"] == 0


def test_live_ats01_conflict_scenario_still_produces_draft():
    """CONFLICT (spec-internal contradiction, not a vendor deviation) should
    still run schedule/retrieval/drafting per README, framed as clarification
    needed rather than a violation."""
    item = next(e for e in EQUIPMENT if e["equipment_id"] == "ATS-01")
    raw_text = (DATASET_DIR / "submittals" / item["raw_submittal_file"]).read_text()
    body = review("ATS-01", raw_text, item["spec_section"])

    assert body["compliance"]["overall_verdict"] == "CONFLICT"
    assert body["draft_rfi"] is not None


def test_live_xfmr01_extraction_noise_filtered_before_compliance():
    """XFMR-01's real datasheet yields ~17 extracted attributes (verified in
    extraction-service's own live tests) but only impedance_pct is spec-
    checkable -- the other ~16 must be filtered, not crash the pipeline, and
    should be visible in pipeline_warnings as informational noise."""
    item = next(e for e in EQUIPMENT if e["equipment_id"] == "XFMR-01")
    raw_text = (DATASET_DIR / "submittals" / item["raw_submittal_file"]).read_text()
    body = review("XFMR-01", raw_text, item["spec_section"])

    assert len(body["extraction"]["extracted_attributes"]) > 1
    assert len(body["compliance"]["results"]) == 1
    assert body["compliance"]["results"][0]["attribute"] == "impedance_pct"
    assert any("not spec-checked" in w for w in body["pipeline_warnings"])


def test_live_unknown_equipment_id_degrades_without_crashing():
    # Reuse XFMR-01's real submittal text so extraction genuinely finds
    # attributes (a blank/generic text would short-circuit on the EARLIER
    # "zero attributes extracted" path instead of exercising the
    # is_known_equipment check this test is actually for).
    item = next(e for e in EQUIPMENT if e["equipment_id"] == "XFMR-01")
    raw_text = (DATASET_DIR / "submittals" / item["raw_submittal_file"]).read_text()
    body = review("EQUIPMENT-THAT-DOES-NOT-EXIST", raw_text)
    assert body["compliance"] is None
    assert body["draft_rfi"] is None
    assert any("not recognized" in w for w in body["pipeline_warnings"])
