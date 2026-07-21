import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.units import merge_unit, normalize_attribute, normalize_whitespace, split_value_and_unit


def test_normalize_whitespace_collapses_multiple_spaces():
    assert normalize_whitespace("a   b\n\tc") == "a b c"


def test_normalize_whitespace_strips_edges():
    assert normalize_whitespace("  hello  ") == "hello"


def test_split_value_and_unit_plain_float_passthrough():
    assert split_value_and_unit(7.0) == (7.0, None)


def test_split_value_and_unit_plain_int_passthrough():
    assert split_value_and_unit(100) == (100, None)


def test_split_value_and_unit_bool_not_treated_as_numeric():
    # bool is a subclass of int in Python -- must not silently become 1/0
    assert split_value_and_unit(True) == (True, None)


def test_split_value_and_unit_string_with_percent():
    assert split_value_and_unit("7.0%") == (7.0, "%")


def test_split_value_and_unit_string_with_unit_and_space():
    assert split_value_and_unit("100 kAIC") == (100, "kAIC")


def test_split_value_and_unit_negative_number():
    assert split_value_and_unit("-5.5 dB") == (-5.5, "dB")


def test_split_value_and_unit_integer_valued_float_becomes_int():
    value, unit = split_value_and_unit("40kA")
    assert value == 40
    assert isinstance(value, int)


def test_split_value_and_unit_non_numeric_string_passthrough():
    assert split_value_and_unit("R-410A") == ("R-410A", None)


def test_split_value_and_unit_plain_number_string_no_unit():
    assert split_value_and_unit("65") == (65, None)


def test_merge_unit_prefers_explicit_unit():
    assert merge_unit("kAIC", "%") == "kAIC"


def test_merge_unit_falls_back_to_split_suffix():
    assert merge_unit(None, "%") == "%"


def test_merge_unit_falls_back_when_explicit_is_empty_string():
    assert merge_unit("", "%") == "%"


def test_merge_unit_none_when_both_missing():
    assert merge_unit(None, None) is None


def test_merge_unit_normalizes_whitespace():
    assert merge_unit("  kA  (3-sec)  ", None) == "kA (3-sec)"


def test_normalize_attribute_splits_and_merges():
    value, unit = normalize_attribute("7.0%", None)
    assert value == 7.0
    assert unit == "%"


def test_normalize_attribute_respects_explicit_unit_over_embedded():
    value, unit = normalize_attribute("100", "kAIC")
    assert value == 100
    assert unit == "kAIC"


def test_normalize_attribute_enum_string_passthrough():
    value, unit = normalize_attribute("R-454B", "refrigerant type")
    assert value == "R-454B"
    assert unit == "refrigerant type"
