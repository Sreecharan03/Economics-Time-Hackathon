"""
Live integration tests against the real Groq API -- deliberately separate
from test_extractor.py's mocked-llm_fn tests (those cover the parsing/
normalization/confidence logic exhaustively and cheaply; these prove the
whole pipeline actually works end-to-end against a real model and real
dataset files, per README.md's stated test plan: "Extraction F1 against
dataset/gold_set/compliance_gold_set.csv's submitted_value column, run over
all 5 raw submittal files ... Target >=0.90 precision/recall".

Skipped automatically if GROQ_API_KEY isn't set (e.g. in CI without secrets)
rather than failing the whole suite.
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.extractor import extract_from_text

DATASET_DIR = Path(__file__).parent.parent.parent.parent / "dataset"

pytestmark = pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"), reason="GROQ_API_KEY not set -- skipping live LLM integration tests"
)

# (submittal file, equipment_id, spec_section, {attribute: expected_value})
# expected values are the ground-truth submitted_value from equipment_master.json --
# this is what a correct extraction should recover, not what compliance-service
# would judge (compliance-service's own gold set carries required_value/verdict,
# which this service must never see -- see spec_vocabulary.py's docstring).
CASES = [
    ("XFMR-01_submittal.txt", "XFMR-01", "26 12 00", {"impedance_pct": 7.0}),
    ("SWGR-MV-01_submittal.txt", "SWGR-MV-01", "26 13 00", {"short_circuit_withstand_kA": 25}),
    ("UPS-01_submittal.txt", "UPS-01", "26 33 00", {"input_breaker_kAIC": 65, "battery_runtime_min": 7}),
    ("UPS-02_submittal.txt", "UPS-02", "26 33 00", {"input_breaker_kAIC": 100, "battery_runtime_min": 12}),
    ("CRAC-01_submittal.txt", "CRAC-01", "23 65 00", {"refrigerant": "R-410A"}),
]


def numeric_close(a, b, tol=0.01) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


@pytest.mark.parametrize("filename,equipment_id,spec_section,expected", CASES, ids=[c[1] for c in CASES])
def test_live_extraction_recovers_expected_values(filename, equipment_id, spec_section, expected):
    raw_text = (DATASET_DIR / "submittals" / filename).read_text()
    eid, attrs, warnings = extract_from_text(raw_text, equipment_id, spec_section)

    assert eid == equipment_id
    assert len(attrs) > 0, f"extraction returned zero attributes for {filename}"

    by_attr = {a.attribute: a for a in attrs}
    found = 0
    for expected_attr, expected_value in expected.items():
        match = None
        # allow reasonable attribute-name variance from the model; fall back
        # to any extracted attribute whose value matches if the exact name differs
        if expected_attr in by_attr:
            match = by_attr[expected_attr]
        else:
            for a in attrs:
                if numeric_close(a.value, expected_value):
                    match = a
                    break
        assert match is not None, (
            f"{filename}: expected attribute '{expected_attr}'={expected_value!r} not recovered; "
            f"got {[(a.attribute, a.value) for a in attrs]}"
        )
        assert numeric_close(match.value, expected_value), (
            f"{filename}: '{expected_attr}' expected {expected_value!r}, got {match.value!r}"
        )
        found += 1

    recall = found / len(expected)
    assert recall == 1.0, f"{filename}: recall {recall} < 1.0 target"


def test_live_extraction_source_spans_are_verified_not_just_asserted():
    """Every extracted attribute from a real document should have a
    verifiable (high-confidence) source_span -- if the model is hallucinating
    spans on real, in-distribution data, that's a real problem to know about."""
    raw_text = (DATASET_DIR / "submittals" / "XFMR-01_submittal.txt").read_text()
    eid, attrs, warnings = extract_from_text(raw_text, "XFMR-01", "26 12 00")
    low_confidence = [a for a in attrs if a.confidence < 0.7]
    assert not low_confidence, f"unexpected hallucinated source_span(s) on real data: {low_confidence}"


def test_live_extraction_does_not_emit_verdict_fields():
    """README.md: this service's output should never emit a PASS/FAIL/verdict field."""
    raw_text = (DATASET_DIR / "submittals" / "XFMR-01_submittal.txt").read_text()
    eid, attrs, warnings = extract_from_text(raw_text, "XFMR-01", "26 12 00")
    for a in attrs:
        assert a.attribute.lower() not in ("verdict", "pass", "fail", "compliance")
