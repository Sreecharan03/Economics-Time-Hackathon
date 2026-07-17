"""
Two layers of coverage for engine.py, per the service README's test plan:

1. Gold-set regression: every PASS/FAIL row in
   dataset/gold_set/compliance_gold_set.csv (both row_types) run through
   check_compliance and asserted to match exactly. Built from each row's own
   columns, independent of spec_data.py, so this tests the engine in
   isolation from how requirements get loaded. CONFLICT (ATS-01) is excluded
   here -- the flat CSV row doesn't carry conflicting_clauses -- and gets
   explicit dedicated tests below plus full round-trip coverage in
   test_api.py (which does go through spec_data.py's real conflicting_clauses
   data).

2. Hypothesis property-based tests: the actual source of edge-case depth.
   Each property is checked against an independently-written reference
   formula, not against the implementation's own logic restated -- so a bug
   in check_compliance's boundary comparison would show up as a property
   violation, not agree with itself.
"""
import csv
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.engine import (
    CheckType,
    ComplianceEngineError,
    ConflictingClause,
    SpecRequirement,
    Verdict,
    check_compliance,
    rollup_verdict,
)

GOLD_SET = Path(__file__).resolve().parents[3] / "dataset" / "gold_set" / "compliance_gold_set.csv"
ENUM_ATTRIBUTES = {"refrigerant", "input_voltage"}


def _load_gold_rows():
    with open(GOLD_SET) as f:
        return list(csv.DictReader(f))


def _requirement_from_row(row: dict) -> SpecRequirement:
    check_type = CheckType.ENUM if row["attribute"] in ENUM_ATTRIBUTES else CheckType.RANGE
    required_value = row["required_value"] or None
    if check_type == CheckType.RANGE and required_value is not None:
        required_value = float(required_value)
    return SpecRequirement(
        attribute=row["attribute"],
        spec_clause="TEST-CLAUSE",
        check_type=check_type,
        unit=row["unit"] or None,
        required_value=required_value,
        acceptable_range_low=float(row["acceptable_range_low"]) if row["acceptable_range_low"] else None,
        acceptable_range_high=float(row["acceptable_range_high"]) if row["acceptable_range_high"] else None,
    )


def _submitted_value_from_row(row: dict):
    if row["attribute"] in ENUM_ATTRIBUTES:
        return row["submitted_value"]
    return float(row["submitted_value"])


_GOLD_ROWS_NON_CONFLICT = [r for r in _load_gold_rows() if r["expected_verdict"] != "CONFLICT"]


@pytest.mark.parametrize(
    "row",
    _GOLD_ROWS_NON_CONFLICT,
    ids=[f"{r['row_type']}:{r['equipment_id']}:{r['attribute']}" for r in _GOLD_ROWS_NON_CONFLICT],
)
def test_gold_set_row(row):
    requirement = _requirement_from_row(row)
    submitted = _submitted_value_from_row(row)
    result = check_compliance(submitted, requirement)
    assert result.verdict.value == row["expected_verdict"], (
        f"{row['equipment_id']}/{row['attribute']}: submitted={submitted} "
        f"expected {row['expected_verdict']} got {result.verdict.value}"
    )


def test_gold_set_has_both_row_types():
    rows = _load_gold_rows()
    row_types = {r["row_type"] for r in rows}
    assert row_types == {"equipment", "boundary_test"}
    assert len(rows) == 21


# ---------------------------------------------------------------------------
# CONFLICT path -- not representable by the flat gold-set CSV row shape, so
# tested directly here with ATS-01's real numbers, and end-to-end (through
# spec_data.py's real conflicting_clauses) in test_api.py.
# ---------------------------------------------------------------------------

def test_conflict_verdict_when_clauses_disagree():
    requirement = SpecRequirement(
        attribute="transfer_time_cycles",
        spec_clause="26 36 00.2",
        check_type=CheckType.RANGE,
        unit="cycles",
        acceptable_range_low=4,
        acceptable_range_high=4,
        conflicting_clauses=(
            ConflictingClause(clause="26 36 00.2", required_value=4, unit="cycles"),
            ConflictingClause(clause="26 05 00 3.4.C", required_value=10, unit="cycles"),
        ),
    )
    result = check_compliance(4, requirement)
    assert result.verdict == Verdict.CONFLICT
    assert "26 36 00.2" in result.rationale
    assert "26 05 00 3.4.C" in result.rationale


def test_conflict_takes_priority_over_range_check():
    """A requirement can't be both a normal RANGE pass/fail AND a CONFLICT --
    conflicting_clauses must always win, regardless of what the value is."""
    requirement = SpecRequirement(
        attribute="x", spec_clause="c", check_type=CheckType.RANGE,
        acceptable_range_low=0, acceptable_range_high=100,
        conflicting_clauses=(ConflictingClause(clause="A", required_value=1),),
    )
    # 50 would clearly PASS a plain [0,100] range check -- must still CONFLICT.
    assert check_compliance(50, requirement).verdict == Verdict.CONFLICT


# ---------------------------------------------------------------------------
# Explicit named edge cases -- documented, meaningful scenarios worth
# pinning down individually rather than leaving purely to property search.
# ---------------------------------------------------------------------------

def test_enum_check_is_case_sensitive():
    """Refrigerant/product codes are conventionally uppercase; a case slip
    could indicate a real data-entry error and should not be silently
    treated as a match."""
    requirement = SpecRequirement(attribute="refrigerant", spec_clause="c", check_type=CheckType.ENUM, required_value="R-454B")
    assert check_compliance("R-454B", requirement).verdict == Verdict.PASS
    assert check_compliance("r-454b", requirement).verdict == Verdict.FAIL


def test_enum_check_trims_whitespace():
    requirement = SpecRequirement(attribute="refrigerant", spec_clause="c", check_type=CheckType.ENUM, required_value="R-454B")
    assert check_compliance("  R-454B  ", requirement).verdict == Verdict.PASS


@pytest.mark.parametrize("bad_value", [True, False])
def test_bool_rejected_for_numeric_check(bad_value):
    """isinstance(True, int) is True in Python -- without an explicit guard,
    a boolean would silently coerce to 1.0/0.0 and pass a range check it has
    no business being compared against."""
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, acceptable_range_low=0, acceptable_range_high=10)
    with pytest.raises(ComplianceEngineError):
        check_compliance(bad_value, requirement)


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_nan_and_inf_rejected(bad_value):
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, acceptable_range_low=0, acceptable_range_high=10)
    with pytest.raises(ComplianceEngineError):
        check_compliance(bad_value, requirement)


def test_none_rejected_for_enum_check():
    requirement = SpecRequirement(attribute="refrigerant", spec_clause="c", check_type=CheckType.ENUM, required_value="R-454B")
    with pytest.raises(ComplianceEngineError):
        check_compliance(None, requirement)


def test_non_numeric_string_rejected_for_range_check():
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, acceptable_range_low=0, acceptable_range_high=10)
    with pytest.raises(ComplianceEngineError):
        check_compliance("not-a-number", requirement)


def test_empty_string_rejected_for_range_check():
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, acceptable_range_low=0, acceptable_range_high=10)
    with pytest.raises(ComplianceEngineError):
        check_compliance("   ", requirement)


def test_range_check_with_no_bounds_raises():
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE)
    with pytest.raises(ComplianceEngineError):
        check_compliance(5, requirement)


def test_unit_mismatch_raises():
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, unit="kA", acceptable_range_low=0, acceptable_range_high=100)
    with pytest.raises(ComplianceEngineError):
        check_compliance(50, requirement, submitted_unit="A")


def test_unit_match_is_case_and_whitespace_insensitive():
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, unit="kA", acceptable_range_low=0, acceptable_range_high=100)
    result = check_compliance(50, requirement, submitted_unit="  KA  ")
    assert result.verdict == Verdict.PASS


class TestRollup:
    def test_all_pass(self):
        assert rollup_verdict([Verdict.PASS, Verdict.PASS]) == Verdict.PASS

    def test_any_fail_wins(self):
        assert rollup_verdict([Verdict.PASS, Verdict.FAIL, Verdict.CONFLICT]) == Verdict.FAIL

    def test_conflict_beats_pass_when_no_fail(self):
        assert rollup_verdict([Verdict.PASS, Verdict.CONFLICT]) == Verdict.CONFLICT

    def test_empty_raises(self):
        with pytest.raises(ComplianceEngineError):
            rollup_verdict([])


# ---------------------------------------------------------------------------
# Hypothesis property-based tests -- this is the actual edge-case-volume
# engine, not the ~30 example-based tests above. Each property is checked
# against an independently-written reference computation, so a bug in the
# implementation's comparison logic would surface as a disagreement, not
# just "the code agrees with itself."
# ---------------------------------------------------------------------------

_FLOAT = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e12, max_value=1e12, width=64)


@settings(max_examples=300)
@given(low=_FLOAT, high=_FLOAT, value=_FLOAT)
def test_property_two_sided_range_matches_reference(low, high, value):
    assume(low <= high)
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, acceptable_range_low=low, acceptable_range_high=high)
    expected = Verdict.PASS if (low <= value <= high) else Verdict.FAIL
    assert check_compliance(value, requirement).verdict == expected


@settings(max_examples=300)
@given(low=_FLOAT, value=_FLOAT)
def test_property_minimum_only_range_matches_reference(low, value):
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, acceptable_range_low=low, acceptable_range_high=None)
    expected = Verdict.PASS if value >= low else Verdict.FAIL
    assert check_compliance(value, requirement).verdict == expected


@settings(max_examples=300)
@given(high=_FLOAT, value=_FLOAT)
def test_property_maximum_only_range_matches_reference(high, value):
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, acceptable_range_low=None, acceptable_range_high=high)
    expected = Verdict.PASS if value <= high else Verdict.FAIL
    assert check_compliance(value, requirement).verdict == expected


@settings(max_examples=200)
@given(low=_FLOAT, high=_FLOAT)
def test_property_exact_boundaries_always_pass(low, high):
    """The tolerance-band edges are inclusive by spec design (ANSI/IEEE
    tolerance language is 'shall not exceed +/-X%', i.e. exactly at the
    limit is compliant) -- this is the property the XFMR-01 boundary_test
    gold-set rows exist to pin down, generalized across arbitrary bounds."""
    assume(low <= high)
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, acceptable_range_low=low, acceptable_range_high=high)
    assert check_compliance(low, requirement).verdict == Verdict.PASS
    assert check_compliance(high, requirement).verdict == Verdict.PASS


@settings(max_examples=200)
@given(value=st.integers(min_value=-10_000_000, max_value=10_000_000))
def test_property_int_float_string_coercion_agree(value):
    """The same numeric value submitted as int, float, or numeric string
    must produce the same verdict -- extraction may hand back any of the
    three depending on how a table cell was parsed, and the engine should
    not care which."""
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, acceptable_range_low=-10_000_001, acceptable_range_high=10_000_001)
    v_int = check_compliance(value, requirement).verdict
    v_float = check_compliance(float(value), requirement).verdict
    v_str = check_compliance(str(value), requirement).verdict
    assert v_int == v_float == v_str


@settings(max_examples=150)
@given(value=_FLOAT, whitespace=st.sampled_from(["", " ", "  ", "\t", "\n "]))
def test_property_numeric_string_whitespace_ignored(value, whitespace):
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, acceptable_range_low=-1e12, acceptable_range_high=1e12)
    padded = f"{whitespace}{value!r}{whitespace}"
    assert check_compliance(padded, requirement).verdict == check_compliance(value, requirement).verdict


@settings(max_examples=150)
@given(text=st.text(min_size=1, max_size=20).filter(lambda s: s.strip()))
def test_property_non_numeric_text_always_rejected(text):
    assume(not _looks_numeric(text))
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.RANGE, acceptable_range_low=0, acceptable_range_high=10)
    with pytest.raises(ComplianceEngineError):
        check_compliance(text, requirement)


def _looks_numeric(s: str) -> bool:
    try:
        float(s.strip())
        return True
    except ValueError:
        return False


@settings(max_examples=100)
@given(s1=st.text(min_size=1, max_size=15), s2=st.text(min_size=1, max_size=15))
def test_property_enum_match_iff_equal_after_strip(s1, s2):
    requirement = SpecRequirement(attribute="x", spec_clause="c", check_type=CheckType.ENUM, required_value=s1.strip())
    assume(s1.strip())  # required_value can't be empty for this property to mean anything
    expected = Verdict.PASS if s2.strip() == s1.strip() else Verdict.FAIL
    assert check_compliance(s2, requirement).verdict == expected
