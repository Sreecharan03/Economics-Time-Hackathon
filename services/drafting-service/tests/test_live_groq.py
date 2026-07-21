"""
Live integration tests -- and not just against Groq in isolation. These call
the REAL compliance-service, schedule-service, and retrieval-service
containers over HTTP to build the request payload, then draft against the
real Groq API. This is the actual cross-domain chain the source evaluation
names as the whole differentiator (spec deviation -> schedule impact ->
commissioning test at risk -> cited RFI) exercised end-to-end, not simulated.

Skipped if GROQ_API_KEY isn't set, or if the three upstream services aren't
reachable (e.g. running this file alone without `docker compose up`).
"""
import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.drafter import draft_rfi
from app.models import DraftRfiRequest

COMPLIANCE_URL = os.environ.get("COMPLIANCE_SERVICE_URL", "http://localhost:8002")
SCHEDULE_URL = os.environ.get("SCHEDULE_SERVICE_URL", "http://localhost:8003")
RETRIEVAL_URL = os.environ.get("RETRIEVAL_SERVICE_URL", "http://localhost:8004")


def _services_reachable() -> bool:
    try:
        for url in (COMPLIANCE_URL, SCHEDULE_URL, RETRIEVAL_URL):
            httpx.get(f"{url}/health", timeout=2.0).raise_for_status()
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="GROQ_API_KEY not set"),
    pytest.mark.skipif(not _services_reachable(), reason="compliance/schedule/retrieval services not reachable"),
]


def build_real_request(equipment_id: str, extracted_attributes: list[dict], query_text: str) -> DraftRfiRequest:
    compliance = httpx.post(
        f"{COMPLIANCE_URL}/compliance/check",
        json={"equipment_id": equipment_id, "extracted_attributes": extracted_attributes},
        timeout=10.0,
    ).json()

    schedule = None
    try:
        schedule = httpx.post(
            f"{SCHEDULE_URL}/schedule/propagate",
            json={"equipment_id": equipment_id, "resubmit_delay_days": 14},
            timeout=10.0,
        ).json()
    except Exception:
        pass

    retrieval = httpx.post(
        f"{RETRIEVAL_URL}/retrieval/similar-rfis", json={"query_text": query_text, "top_k": 1}, timeout=10.0
    ).json()

    return DraftRfiRequest(
        equipment_id=equipment_id,
        compliance_result=compliance,
        schedule_result=schedule,
        precedent=retrieval["results"],
    )


def test_live_draft_xfmr01_critical_scenario():
    """The hero scenario: real compliance FAIL + real schedule CRITICAL slip
    + real retrieved precedent, drafted for real."""
    req = build_real_request(
        "XFMR-01",
        [{"attribute": "impedance_pct", "value": 7.0, "unit": "%"}],
        "transformer impedance outside coordination study tolerance",
    )
    assert req.compliance_result.overall_verdict == "FAIL"
    assert req.schedule_result.urgency == "CRITICAL"
    assert req.precedent[0].rfi_id == "RFI-HIST-003"

    body, warnings = draft_rfi(req)

    assert warnings == [], f"unexpected dropped/hallucinated citations: {warnings}"
    assert len(body.citations) >= 1
    cited_types = {c.type for c in body.citations}
    assert "spec_clause" in cited_types
    # the draft should actually mention the real submitted value, not a paraphrase-only summary
    assert "7.0" in body.body or "7%" in body.body


def test_live_draft_swgr01_flagged_not_critical_scenario():
    """The 'don't cry wolf' scenario: verifies the draft's tone/content
    reflects FLAGGED (not CRITICAL) urgency when float absorbs the delay."""
    req = build_real_request(
        "SWGR-MV-01",
        [{"attribute": "short_circuit_withstand_kA", "value": 25, "unit": "kA (3-sec)"}],
        "medium voltage switchgear short circuit withstand rating below fault study",
    )
    assert req.compliance_result.overall_verdict == "FAIL"
    assert req.schedule_result.urgency == "FLAGGED"

    body, warnings = draft_rfi(req)
    assert warnings == []
    assert len(body.citations) >= 1


def test_live_draft_all_citations_resolve_to_payload_structurally():
    """The README's own stated test bar: every citation must resolve to a
    real field in the input, checked structurally -- not prose quality."""
    from app.drafter import collect_valid_refs

    req = build_real_request(
        "XFMR-01",
        [{"attribute": "impedance_pct", "value": 7.0, "unit": "%"}],
        "transformer impedance tolerance",
    )
    body, warnings = draft_rfi(req)
    valid_refs = collect_valid_refs(req)
    for c in body.citations:
        assert c.ref in valid_refs.get(c.type, set()), f"citation {c} does not structurally resolve to the payload"


def test_live_draft_always_requires_human_approval():
    req = build_real_request(
        "XFMR-01", [{"attribute": "impedance_pct", "value": 7.0, "unit": "%"}], "transformer impedance tolerance"
    )
    body, warnings = draft_rfi(req)
    # requires_human_approval is hardcoded True in main.py regardless of draft
    # content -- this test documents that invariant at the drafter level via
    # the fact that no field in DraftRfiBody can waive it.
    assert not hasattr(body, "requires_human_approval")
