"""
Mocked edge-case suite for the orchestrator -- no real network calls, no
real services required. Every downstream HTTP call is intercepted via
httpx.MockTransport so each test controls exactly what each of the five
services returns (success, various error codes, or a simulated connection
failure), independent of whether those services happen to be running.

Real dataset/submittals/equipment_master.json is used for the
spec_filter checkable-attribute lookup (not mocked) -- that's the actual
data the filtering bug (see spec_filter.py's docstring) depends on, so
faking it would test nothing real.
"""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.orchestrator import GatewayError, review_submittal

EXTRACTION_PATH = "/extraction/submittal"
COMPLIANCE_PATH = "/compliance/check"
SCHEDULE_PATH = "/schedule/propagate"
RETRIEVAL_PATH = "/retrieval/similar-rfis"
DRAFTING_PATH = "/drafting/rfi"


def json_response(status_code: int, body: dict) -> httpx.Response:
    return httpx.Response(status_code, json=body)


class Router:
    """Maps request path -> a response, an exception to raise, or a
    recording callable. Tracks every path hit for call-count assertions."""

    def __init__(self):
        self.routes: dict[str, httpx.Response | Exception] = {}
        self.calls: list[str] = []

    def on(self, path: str, response_or_exc: httpx.Response | Exception):
        self.routes[path] = response_or_exc
        return self

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append(path)
        if path not in self.routes:
            raise AssertionError(f"unexpected request to {path} (registered: {list(self.routes)})")
        result = self.routes[path]
        if isinstance(result, Exception):
            raise result
        return result

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


# --- fixtures: canonical response bodies mirroring the real services' shapes ---

def extraction_ok(attrs=None, equipment_id="XFMR-01"):
    return {
        "equipment_id": equipment_id,
        "extracted_attributes": attrs if attrs is not None else [
            {"attribute": "impedance_pct", "value": 7.0, "unit": "%", "source_span": "Impedance 7.0%", "confidence": 0.95}
        ],
        "extraction_warnings": [],
    }


def compliance_body(verdict, attribute="impedance_pct", rationale="exceeds tolerance", equipment_id="XFMR-01"):
    return {
        "equipment_id": equipment_id,
        "overall_verdict": verdict,
        "results": [
            {
                "attribute": attribute,
                "submitted_value": 7.0,
                "required_value": 5.75,
                "unit": "%",
                "verdict": verdict if verdict != "PASS" else "PASS",
                "spec_section": "26 12 00.3",
                "rationale": rationale,
            }
        ],
    }


SCHEDULE_OK = {
    "triggering_activity": "SUBM-XFMR-01",
    "milestone_impact": {
        "activity_id": "CX-L5-IST", "activity_name": "IST", "baseline_early_finish": 745,
        "new_early_finish": 759, "slip_days": 14, "critical": True,
    },
    "affected_activities": [],
    "urgency": "CRITICAL",
}

RETRIEVAL_OK = {"results": [{"rfi_id": "RFI-HIST-003", "source_project": "Ashburn", "subject": "s", "score": 0.9, "resolution": "r"}]}

DRAFTING_OK = {
    "draft_rfi": {"subject": "s", "body": "b", "citations": [{"type": "spec_clause", "ref": "26 12 00.3"}]},
    "requires_human_approval": True,
    "draft_warnings": [],
}


# --- happy paths -----------------------------------------------------------


async def test_pass_verdict_skips_schedule_retrieval_drafting():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("PASS")))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["compliance"]["overall_verdict"] == "PASS"
    assert result["schedule"] is None
    assert result["precedent"] == []
    assert result["draft_rfi"] is None
    assert SCHEDULE_PATH not in router.calls
    assert RETRIEVAL_PATH not in router.calls
    assert DRAFTING_PATH not in router.calls


async def test_fail_verdict_calls_all_five_services():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, json_response(200, SCHEDULE_OK))
    router.on(RETRIEVAL_PATH, json_response(200, RETRIEVAL_OK))
    router.on(DRAFTING_PATH, json_response(200, DRAFTING_OK))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["schedule"]["urgency"] == "CRITICAL"
    assert result["precedent"][0]["rfi_id"] == "RFI-HIST-003"
    assert result["draft_rfi"]["subject"] == "s"
    assert set(router.calls) == {EXTRACTION_PATH, COMPLIANCE_PATH, SCHEDULE_PATH, RETRIEVAL_PATH, DRAFTING_PATH}


async def test_conflict_verdict_also_calls_schedule_retrieval_drafting():
    """README: CONFLICT (spec-internal contradiction) still runs steps 3-4,
    same as FAIL -- only PASS skips them."""
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok(
        [{"attribute": "transfer_time_cycles", "value": 4, "unit": "cycles", "source_span": "x", "confidence": 0.9}],
        equipment_id="ATS-01",
    )))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body(
        "CONFLICT", attribute="transfer_time_cycles", rationale="spec self-contradicts", equipment_id="ATS-01"
    )))
    router.on(SCHEDULE_PATH, json_response(200, SCHEDULE_OK))
    router.on(RETRIEVAL_PATH, json_response(200, RETRIEVAL_OK))
    router.on(DRAFTING_PATH, json_response(200, DRAFTING_OK))
    async with router.client() as client:
        result = await review_submittal(client, "ATS-01", "some text")
    assert result["compliance"]["overall_verdict"] == "CONFLICT"
    assert SCHEDULE_PATH in router.calls
    assert RETRIEVAL_PATH in router.calls
    assert DRAFTING_PATH in router.calls


# --- extraction-service edge cases -----------------------------------------


async def test_extraction_unreachable_raises_503():
    router = Router()
    router.on(EXTRACTION_PATH, httpx.ConnectError("connection refused"))
    async with router.client() as client:
        with pytest.raises(GatewayError) as exc_info:
            await review_submittal(client, "XFMR-01", "some text")
    assert exc_info.value.status_code == 503


async def test_extraction_501_no_groq_key_raises_502():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(501, {"detail": "GROQ_API_KEY not set"}))
    async with router.client() as client:
        with pytest.raises(GatewayError) as exc_info:
            await review_submittal(client, "XFMR-01", "some text")
    assert exc_info.value.status_code == 502


async def test_extraction_zero_attributes_short_circuits_before_compliance():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok(attrs=[])))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["compliance"] is None
    assert "cannot assess compliance" in result["pipeline_warnings"][0]
    assert COMPLIANCE_PATH not in router.calls


# --- the real filtering bug (spec_filter.py) --------------------------------


async def test_mixed_checkable_and_uncheckable_attributes_filters_before_compliance():
    """The real bug: extraction returns attributes compliance-service doesn't
    track (e.g. rated_power for a transformer). Only impedance_pct should
    reach compliance-service; the rest surface as an informational warning,
    not a 404."""
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok(attrs=[
        {"attribute": "rated_power", "value": 2500, "unit": "kVA", "source_span": "x", "confidence": 0.95},
        {"attribute": "impedance_pct", "value": 7.0, "unit": "%", "source_span": "y", "confidence": 0.95},
        {"attribute": "vector_group", "value": "Dyn11", "unit": None, "source_span": "z", "confidence": 0.95},
    ])))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, json_response(200, SCHEDULE_OK))
    router.on(RETRIEVAL_PATH, json_response(200, RETRIEVAL_OK))
    router.on(DRAFTING_PATH, json_response(200, DRAFTING_OK))

    captured_request = {}
    original_handler = router.handler

    def capturing_handler(request):
        if request.url.path == COMPLIANCE_PATH:
            import json as _json
            captured_request["body"] = _json.loads(request.content)
        return original_handler(request)

    router.handler = capturing_handler

    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")

    sent_attrs = [a["attribute"] for a in captured_request["body"]["extracted_attributes"]]
    assert sent_attrs == ["impedance_pct"]
    assert any("not spec-checked" in w for w in result["pipeline_warnings"])
    assert "rated_power" in str(result["pipeline_warnings"])
    assert "vector_group" in str(result["pipeline_warnings"])


async def test_all_attributes_uncheckable_short_circuits_before_compliance():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok(attrs=[
        {"attribute": "rated_power", "value": 2500, "unit": "kVA", "source_span": "x", "confidence": 0.95},
    ])))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["compliance"] is None
    assert COMPLIANCE_PATH not in router.calls
    assert "none match a checkable" in result["pipeline_warnings"][0]


async def test_duplicate_attribute_extractions_keep_only_highest_confidence():
    """Real observed failure mode: prose mentioning a sibling equipment's or
    the spec minimum's value under the same attribute name gets extracted as
    extra 'readings', dragging an otherwise-correct value's verdict down via
    an unrelated number. Only the highest-confidence entry should reach
    compliance-service."""
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok(attrs=[
        {"attribute": "impedance_pct", "value": 5.9, "unit": "%", "source_span": "low conf", "confidence": 0.7},
        {"attribute": "impedance_pct", "value": 7.0, "unit": "%", "source_span": "high conf", "confidence": 0.95},
    ])))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, json_response(200, SCHEDULE_OK))
    router.on(RETRIEVAL_PATH, json_response(200, RETRIEVAL_OK))
    router.on(DRAFTING_PATH, json_response(200, DRAFTING_OK))

    captured = {}
    original_handler = router.handler

    def capturing_handler(request):
        if request.url.path == COMPLIANCE_PATH:
            import json as _json
            captured["body"] = _json.loads(request.content)
        return original_handler(request)

    router.handler = capturing_handler

    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")

    sent = captured["body"]["extracted_attributes"]
    assert len(sent) == 1
    assert sent[0]["value"] == 7.0  # the higher-confidence entry, not the first one
    assert any("distinct values extracted for one attribute" in w for w in result["pipeline_warnings"])


async def test_unknown_equipment_id_short_circuits_before_compliance():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, {
        "equipment_id": "FAKE-EQUIPMENT-999",
        "extracted_attributes": [{"attribute": "impedance_pct", "value": 7.0, "unit": "%", "source_span": "x", "confidence": 0.9}],
        "extraction_warnings": [],
    }))
    async with router.client() as client:
        result = await review_submittal(client, "FAKE-EQUIPMENT-999", "some text")
    assert result["compliance"] is None
    assert COMPLIANCE_PATH not in router.calls
    assert "not recognized" in result["pipeline_warnings"][0]


# --- compliance-service edge cases ------------------------------------------


async def test_compliance_unreachable_raises_503():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, httpx.ConnectError("connection refused"))
    async with router.client() as client:
        with pytest.raises(GatewayError) as exc_info:
            await review_submittal(client, "XFMR-01", "some text")
    assert exc_info.value.status_code == 503


async def test_compliance_unexpected_404_raises_502_not_swallowed():
    """Shouldn't happen given the filter, but if compliance-service's seed
    data and the filter ever drift, this must surface as a gateway bug, not
    silently degrade."""
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(404, {"detail": "no spec requirement"}))
    async with router.client() as client:
        with pytest.raises(GatewayError) as exc_info:
            await review_submittal(client, "XFMR-01", "some text")
    assert exc_info.value.status_code == 502


# --- schedule-service edge cases (best-effort) ------------------------------


async def test_schedule_404_degrades_gracefully_pipeline_continues():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, json_response(404, {"detail": "no submittal activity"}))
    router.on(RETRIEVAL_PATH, json_response(200, RETRIEVAL_OK))
    router.on(DRAFTING_PATH, json_response(200, DRAFTING_OK))
    async with router.client() as client:
        result = await review_submittal(client, "PDU-01", "some text")
    assert result["schedule"] is None
    assert any("no schedule activity linked" in w for w in result["pipeline_warnings"])
    # pipeline must continue -- retrieval and drafting still run
    assert result["draft_rfi"] is not None


async def test_schedule_unreachable_degrades_gracefully():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, httpx.ConnectError("connection refused"))
    router.on(RETRIEVAL_PATH, json_response(200, RETRIEVAL_OK))
    router.on(DRAFTING_PATH, json_response(200, DRAFTING_OK))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["schedule"] is None
    assert any("schedule-service unavailable" in w for w in result["pipeline_warnings"])
    assert result["draft_rfi"] is not None


async def test_schedule_500_degrades_gracefully():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, json_response(500, {"detail": "internal error"}))
    router.on(RETRIEVAL_PATH, json_response(200, RETRIEVAL_OK))
    router.on(DRAFTING_PATH, json_response(200, DRAFTING_OK))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["schedule"] is None
    assert any("schedule-service error (500)" in w for w in result["pipeline_warnings"])


# --- retrieval-service edge cases (best-effort) -----------------------------


async def test_retrieval_unreachable_degrades_gracefully_drafting_still_runs():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, json_response(200, SCHEDULE_OK))
    router.on(RETRIEVAL_PATH, httpx.ConnectError("connection refused"))
    router.on(DRAFTING_PATH, json_response(200, DRAFTING_OK))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["precedent"] == []
    assert any("retrieval-service unavailable" in w for w in result["pipeline_warnings"])
    assert result["draft_rfi"] is not None
    assert DRAFTING_PATH in router.calls


async def test_retrieval_returns_empty_results_no_warning_needed():
    """Zero matches is a valid, non-error outcome -- must not be conflated
    with a service failure warning."""
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, json_response(200, SCHEDULE_OK))
    router.on(RETRIEVAL_PATH, json_response(200, {"results": []}))
    router.on(DRAFTING_PATH, json_response(200, DRAFTING_OK))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["precedent"] == []
    assert not any("retrieval" in w for w in result["pipeline_warnings"])


# --- both schedule AND retrieval fail simultaneously (concurrency + degradation) --


async def test_schedule_and_retrieval_both_fail_drafting_still_attempted():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, httpx.ConnectError("down"))
    router.on(RETRIEVAL_PATH, httpx.ConnectError("down"))
    router.on(DRAFTING_PATH, json_response(200, DRAFTING_OK))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["schedule"] is None
    assert result["precedent"] == []
    assert result["draft_rfi"] is not None  # drafting-service accepts schedule_result=None, precedent=[]
    assert len([w for w in result["pipeline_warnings"] if "unavailable" in w]) == 2


# --- drafting-service edge cases (best-effort) ------------------------------


async def test_drafting_unreachable_still_returns_200_with_null_draft():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, json_response(200, SCHEDULE_OK))
    router.on(RETRIEVAL_PATH, json_response(200, RETRIEVAL_OK))
    router.on(DRAFTING_PATH, httpx.ConnectError("connection refused"))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["draft_rfi"] is None
    assert any("drafting-service unavailable" in w for w in result["pipeline_warnings"])
    # the rest of the review is still fully populated and useful
    assert result["compliance"]["overall_verdict"] == "FAIL"
    assert result["schedule"]["urgency"] == "CRITICAL"


async def test_drafting_502_malformed_llm_output_degrades_gracefully():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, json_response(200, SCHEDULE_OK))
    router.on(RETRIEVAL_PATH, json_response(200, RETRIEVAL_OK))
    router.on(DRAFTING_PATH, json_response(502, {"detail": "LLM returned unusable output"}))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["draft_rfi"] is None
    assert any("drafting-service error (502)" in w for w in result["pipeline_warnings"])


async def test_drafting_warnings_propagate_into_pipeline_warnings():
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body("FAIL")))
    router.on(SCHEDULE_PATH, json_response(200, SCHEDULE_OK))
    router.on(RETRIEVAL_PATH, json_response(200, RETRIEVAL_OK))
    drafting_with_warning = {**DRAFTING_OK, "draft_warnings": ["citation (spec_clause, 'invented') dropped"]}
    router.on(DRAFTING_PATH, json_response(200, drafting_with_warning))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert "citation (spec_clause, 'invented') dropped" in result["pipeline_warnings"]


# --- requires_human_approval invariant --------------------------------------


@pytest.mark.parametrize("verdict", ["PASS", "FAIL", "CONFLICT"])
async def test_requires_human_approval_always_true(verdict):
    router = Router()
    router.on(EXTRACTION_PATH, json_response(200, extraction_ok()))
    router.on(COMPLIANCE_PATH, json_response(200, compliance_body(verdict)))
    if verdict != "PASS":
        router.on(SCHEDULE_PATH, json_response(200, SCHEDULE_OK))
        router.on(RETRIEVAL_PATH, json_response(200, RETRIEVAL_OK))
        router.on(DRAFTING_PATH, json_response(200, DRAFTING_OK))
    async with router.client() as client:
        result = await review_submittal(client, "XFMR-01", "some text")
    assert result["requires_human_approval"] is True
