import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.drafter import DraftingError, collect_valid_refs, draft_rfi, parse_llm_json, validate_citations

# --- parse_llm_json ---------------------------------------------------


def test_parse_llm_json_plain():
    parsed = parse_llm_json('{"subject": "s", "body": "b", "citations": []}')
    assert parsed["subject"] == "s"


def test_parse_llm_json_with_markdown_fence():
    raw = '```json\n{"subject": "s", "body": "b", "citations": []}\n```'
    assert parse_llm_json(raw)["subject"] == "s"


def test_parse_llm_json_malformed_raises():
    with pytest.raises(DraftingError):
        parse_llm_json("not json {{{")


def test_parse_llm_json_missing_subject_raises():
    with pytest.raises(DraftingError):
        parse_llm_json('{"body": "b", "citations": []}')


def test_parse_llm_json_missing_body_raises():
    with pytest.raises(DraftingError):
        parse_llm_json('{"subject": "s", "citations": []}')


def test_parse_llm_json_missing_citations_raises():
    with pytest.raises(DraftingError):
        parse_llm_json('{"subject": "s", "body": "b"}')


def test_parse_llm_json_citations_not_a_list_raises():
    with pytest.raises(DraftingError):
        parse_llm_json('{"subject": "s", "body": "b", "citations": "nope"}')


# --- collect_valid_refs -------------------------------------------------


def test_collect_valid_refs_includes_spec_section(xfmr01_request):
    refs = collect_valid_refs(xfmr01_request)
    assert "26 12 00.3" in refs["spec_clause"]


def test_collect_valid_refs_includes_equipment_id(xfmr01_request):
    refs = collect_valid_refs(xfmr01_request)
    assert "XFMR-01" in refs["submittal"]


def test_collect_valid_refs_includes_schedule_activities(xfmr01_request):
    refs = collect_valid_refs(xfmr01_request)
    assert "SUBM-XFMR-01" in refs["schedule_activity"]
    assert "CX-L5-IST" in refs["schedule_activity"]


def test_collect_valid_refs_includes_precedent_rfi(xfmr01_request):
    refs = collect_valid_refs(xfmr01_request)
    assert "RFI-HIST-003" in refs["precedent_rfi"]


def test_collect_valid_refs_empty_schedule_activity_when_no_schedule_result(xfmr01_request):
    xfmr01_request.schedule_result = None
    refs = collect_valid_refs(xfmr01_request)
    assert refs["schedule_activity"] == set()


# --- validate_citations --------------------------------------------------


def test_validate_citations_keeps_valid(xfmr01_request):
    refs = collect_valid_refs(xfmr01_request)
    kept, warnings = validate_citations([{"type": "spec_clause", "ref": "26 12 00.3"}], refs)
    assert len(kept) == 1
    assert warnings == []


def test_validate_citations_drops_unresolvable_ref(xfmr01_request):
    refs = collect_valid_refs(xfmr01_request)
    kept, warnings = validate_citations([{"type": "spec_clause", "ref": "99 99 99.9"}], refs)
    assert kept == []
    assert len(warnings) == 1
    assert "does not resolve" in warnings[0]


def test_validate_citations_drops_wrong_type(xfmr01_request):
    """A real spec_section value cited under the wrong `type` should still be rejected."""
    refs = collect_valid_refs(xfmr01_request)
    kept, warnings = validate_citations([{"type": "precedent_rfi", "ref": "26 12 00.3"}], refs)
    assert kept == []


def test_validate_citations_missing_fields_dropped_not_crashed(xfmr01_request):
    refs = collect_valid_refs(xfmr01_request)
    kept, warnings = validate_citations([{"type": "spec_clause"}], refs)
    assert kept == []
    assert "missing type/ref" in warnings[0]


def test_validate_citations_unknown_type_dropped(xfmr01_request):
    refs = collect_valid_refs(xfmr01_request)
    kept, warnings = validate_citations([{"type": "made_up_type", "ref": "XFMR-01"}], refs)
    assert kept == []


def test_validate_citations_mixed_valid_and_invalid(xfmr01_request):
    refs = collect_valid_refs(xfmr01_request)
    kept, warnings = validate_citations(
        [
            {"type": "spec_clause", "ref": "26 12 00.3"},
            {"type": "spec_clause", "ref": "fabricated"},
            {"type": "precedent_rfi", "ref": "RFI-HIST-003"},
        ],
        refs,
    )
    assert len(kept) == 2
    assert len(warnings) == 1


# --- draft_rfi (fake llm_fn) ----------------------------------------------


def make_fake_llm(response: dict):
    return lambda system_prompt, user_content: json.dumps(response)


def test_draft_rfi_happy_path(xfmr01_request):
    fake = make_fake_llm(
        {
            "subject": "XFMR-01 impedance deviation",
            "body": "The submitted transformer impedance of 7.0% exceeds spec. Human sign-off required.",
            "citations": [
                {"type": "spec_clause", "ref": "26 12 00.3"},
                {"type": "precedent_rfi", "ref": "RFI-HIST-003"},
            ],
        }
    )
    body, warnings = draft_rfi(xfmr01_request, llm_fn=fake)
    assert body.subject == "XFMR-01 impedance deviation"
    assert len(body.citations) == 2
    assert warnings == []


def test_draft_rfi_drops_hallucinated_citation(xfmr01_request):
    fake = make_fake_llm(
        {
            "subject": "s",
            "body": "b",
            "citations": [{"type": "spec_clause", "ref": "26 12 00.3"}, {"type": "spec_clause", "ref": "invented"}],
        }
    )
    body, warnings = draft_rfi(xfmr01_request, llm_fn=fake)
    assert len(body.citations) == 1
    assert len(warnings) == 1


def test_draft_rfi_malformed_llm_output_raises(xfmr01_request):
    fake = lambda sp, uc: "not json"
    with pytest.raises(DraftingError):
        draft_rfi(xfmr01_request, llm_fn=fake)


def test_draft_rfi_no_precedent_still_works(xfmr01_request):
    xfmr01_request.precedent = []
    fake = make_fake_llm({"subject": "s", "body": "b", "citations": [{"type": "spec_clause", "ref": "26 12 00.3"}]})
    body, warnings = draft_rfi(xfmr01_request, llm_fn=fake)
    assert len(body.citations) == 1


def test_draft_rfi_no_schedule_result_still_works(xfmr01_request):
    xfmr01_request.schedule_result = None
    fake = make_fake_llm({"subject": "s", "body": "b", "citations": [{"type": "submittal", "ref": "XFMR-01"}]})
    body, warnings = draft_rfi(xfmr01_request, llm_fn=fake)
    assert len(body.citations) == 1


def test_draft_rfi_empty_citations_list_ok(xfmr01_request):
    fake = make_fake_llm({"subject": "s", "body": "b", "citations": []})
    body, warnings = draft_rfi(xfmr01_request, llm_fn=fake)
    assert body.citations == []
    assert warnings == []
