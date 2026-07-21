"""
Deterministic units normalization -- plain Python, no model call, per
README.md's pipeline step 4. The LLM sometimes embeds the unit in the value
string (e.g. "7.0%" instead of value=7.0, unit="%") despite being told not
to; this cleans that up rather than trusting the model's own separation.
"""
import re

_NUMERIC_RE = re.compile(r"^\s*(-?\d+\.?\d*)\s*(.*?)\s*$")


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def split_value_and_unit(raw_value) -> tuple[float | str, str | None]:
    """If raw_value is a string with a trailing unit-looking suffix (e.g.
    "7.0%", "100 kAIC"), split it into (numeric_value, suffix). Returns the
    original value unchanged if it isn't a numeric-with-suffix string."""
    if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
        return raw_value, None
    if not isinstance(raw_value, str):
        return raw_value, None

    m = _NUMERIC_RE.match(raw_value)
    if not m:
        return raw_value, None
    number_part, suffix = m.group(1), m.group(2)
    try:
        value = float(number_part)
        if value.is_integer():
            value = int(value)
    except ValueError:
        return raw_value, None
    return value, (suffix or None)


def merge_unit(extracted_unit: str | None, split_suffix: str | None) -> str | None:
    """Prefer the model's own `unit` field when given; fall back to a suffix
    recovered from the value string; normalize whitespace either way."""
    chosen = extracted_unit if extracted_unit not in (None, "") else split_suffix
    if chosen is None:
        return None
    return normalize_whitespace(chosen)


def normalize_attribute(value, unit: str | None) -> tuple[float | int | str, str | None]:
    clean_value, split_suffix = split_value_and_unit(value)
    clean_unit = merge_unit(unit, split_suffix)
    if isinstance(clean_value, str):
        clean_value = normalize_whitespace(clean_value)
    return clean_value, clean_unit
