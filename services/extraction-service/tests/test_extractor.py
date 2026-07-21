import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.extractor import (
    ExtractionError,
    confidence_for_span,
    extract_from_text,
    parse_llm_json,
    verify_source_span,
)

SAMPLE_TEXT = "Impedance (Z%): 7.0% at rated tap, measured per factory routine test.\nSound Level: 68 dB(A) at 1m"


# --- parse_llm_json -----------------------------------------------------


def test_parse_llm_json_plain():
    parsed = parse_llm_json('{"attributes": []}')
    assert parsed == {"attributes": []}


def test_parse_llm_json_with_markdown_fence():
    raw = '```json\n{"attributes": [{"attribute": "x"}]}\n```'
    parsed = parse_llm_json(raw)
    assert parsed["attributes"][0]["attribute"] == "x"


def test_parse_llm_json_with_bare_fence_no_json_tag():
    raw = '```\n{"attributes": []}\n```'
    assert parse_llm_json(raw) == {"attributes": []}


def test_parse_llm_json_with_surrounding_prose_and_fence():
    raw = 'Here is the extraction:\n```json\n{"attributes": []}\n```\nLet me know if you need more.'
    assert parse_llm_json(raw) == {"attributes": []}


def test_parse_llm_json_malformed_raises_extraction_error():
    with pytest.raises(ExtractionError):
        parse_llm_json("not json at all {{{")


def test_parse_llm_json_missing_attributes_key_raises():
    with pytest.raises(ExtractionError):
        parse_llm_json('{"foo": "bar"}')


def test_parse_llm_json_attributes_not_a_list_raises():
    with pytest.raises(ExtractionError):
        parse_llm_json('{"attributes": "not a list"}')


def test_parse_llm_json_top_level_not_object_raises():
    with pytest.raises(ExtractionError):
        parse_llm_json("[1, 2, 3]")


# --- verify_source_span ---------------------------------------------------


def test_verify_source_span_exact_match():
    exact, fuzzy = verify_source_span("Impedance (Z%): 7.0% at rated tap", SAMPLE_TEXT)
    assert exact is True
    assert fuzzy is True


def test_verify_source_span_whitespace_normalized_match():
    exact, fuzzy = verify_source_span("Impedance (Z%):   7.0%   at rated tap", SAMPLE_TEXT)
    assert exact is True


def test_verify_source_span_case_insensitive_only():
    exact, fuzzy = verify_source_span("impedance (z%): 7.0% at rated tap", SAMPLE_TEXT)
    assert exact is False
    assert fuzzy is True


def test_verify_source_span_not_found():
    exact, fuzzy = verify_source_span("this text does not appear anywhere", SAMPLE_TEXT)
    assert exact is False
    assert fuzzy is False


def test_confidence_for_span_exact():
    assert confidence_for_span(True, True) == 0.95


def test_confidence_for_span_fuzzy_only():
    assert confidence_for_span(False, True) == 0.7


def test_confidence_for_span_not_found():
    assert confidence_for_span(False, False) == 0.3


# --- extract_from_text (with injected fake llm_fn) -------------------------


def make_fake_llm(response_json: dict):
    def fake(system_prompt, user_content):
        return json.dumps(response_json)
    return fake


def test_extract_from_text_happy_path():
    fake = make_fake_llm(
        {
            "attributes": [
                {"attribute": "impedance_pct", "value": "7.0%", "source_span": "Impedance (Z%): 7.0% at rated tap"}
            ]
        }
    )
    eid, attrs, warnings = extract_from_text(SAMPLE_TEXT, "XFMR-01", "26 12 00", llm_fn=fake)
    assert eid == "XFMR-01"
    assert len(attrs) == 1
    assert attrs[0].attribute == "impedance_pct"
    assert attrs[0].value == 7.0
    assert attrs[0].unit == "%"
    assert attrs[0].confidence == 0.95
    assert warnings == []


def test_extract_from_text_hallucinated_source_span_flagged():
    fake = make_fake_llm(
        {"attributes": [{"attribute": "impedance_pct", "value": 7.0, "source_span": "this was never in the document"}]}
    )
    eid, attrs, warnings = extract_from_text(SAMPLE_TEXT, llm_fn=fake)
    assert attrs[0].confidence == 0.3
    assert any("hallucination" in w for w in warnings)


def test_extract_from_text_missing_required_field_skipped_not_crashed():
    fake = make_fake_llm({"attributes": [{"attribute": "impedance_pct"}]})  # missing value + source_span
    eid, attrs, warnings = extract_from_text(SAMPLE_TEXT, llm_fn=fake)
    assert attrs == []
    assert any("missing required field" in w for w in warnings)


def test_extract_from_text_empty_attributes_list_warns():
    fake = make_fake_llm({"attributes": []})
    eid, attrs, warnings = extract_from_text(SAMPLE_TEXT, llm_fn=fake)
    assert attrs == []
    assert any("no attributes extracted" in w for w in warnings)


def test_extract_from_text_malformed_llm_output_raises():
    fake = lambda sp, uc: "not valid json"
    with pytest.raises(ExtractionError):
        extract_from_text(SAMPLE_TEXT, llm_fn=fake)


def test_extract_from_text_no_equipment_id_hint_passthrough_none():
    fake = make_fake_llm({"attributes": []})
    eid, attrs, warnings = extract_from_text(SAMPLE_TEXT, equipment_id_hint=None, llm_fn=fake)
    assert eid is None


def test_extract_from_text_multiple_attributes_mixed_confidence():
    fake = make_fake_llm(
        {
            "attributes": [
                {"attribute": "a", "value": "1%", "source_span": "Impedance (Z%): 7.0% at rated tap"},
                {"attribute": "b", "value": 2, "source_span": "totally fabricated span"},
            ]
        }
    )
    eid, attrs, warnings = extract_from_text(SAMPLE_TEXT, llm_fn=fake)
    assert len(attrs) == 2
    assert attrs[0].confidence == 0.95
    assert attrs[1].confidence == 0.3
    assert len(warnings) == 1  # only the second one should warn


def test_extract_from_text_case_insensitive_span_flagged_but_kept():
    fake = make_fake_llm(
        {"attributes": [{"attribute": "impedance_pct", "value": 7.0, "source_span": "IMPEDANCE (Z%): 7.0% AT RATED TAP"}]}
    )
    eid, attrs, warnings = extract_from_text(SAMPLE_TEXT, llm_fn=fake)
    assert len(attrs) == 1  # still kept, just lower confidence
    assert attrs[0].confidence == 0.7
    assert any("case-insensitively" in w for w in warnings)


def test_extract_from_text_preserves_enum_values_as_strings():
    fake = make_fake_llm(
        {"attributes": [{"attribute": "refrigerant", "value": "R-410A", "unit": "refrigerant type",
                          "source_span": "Impedance (Z%): 7.0% at rated tap"}]}
    )
    eid, attrs, warnings = extract_from_text(SAMPLE_TEXT, llm_fn=fake)
    assert attrs[0].value == "R-410A"
    assert attrs[0].unit == "refrigerant type"
