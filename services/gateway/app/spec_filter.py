"""
Bridges real schema mismatches between extraction-service and
compliance-service -- both independently built, independently tested, and
each behaving exactly as documented in isolation. Three distinct mismatches
only show up when they're actually chained together, which is the whole
reason a live full-pipeline test (not just per-service unit tests) matters:

1. COVERAGE mismatch: extraction-service pulls out EVERY spec value present
   on a datasheet (17 attributes for the real XFMR-01 submittal), but
   compliance-service's spec_requirement data (loaded from the same
   dataset/submittals/equipment_master.json) only tracks the handful of
   attributes actually listed in each equipment's `attributes[]` array --
   for XFMR-01, just `impedance_pct`. compliance-service's /compliance/check
   loops over every attribute in the request and 404s on the FIRST one it
   doesn't recognize for that equipment_id (see compliance-service's
   spec_data.get_requirement) -- it does not skip unknowns.

2. UNIT LABEL mismatch: compliance-service's engine.py refuses to compare
   values whose units don't match the spec requirement's unit string
   exactly (case-insensitive, trimmed -- but not a substring/prefix match).
   That's a deliberate, tested guard in compliance-service (real bug: "kW"
   from a real Caterpillar datasheet vs the spec's "kW standby" label 502'd
   the whole GEN-01/GEN-02 pipeline on first live run). Since the gateway
   already loads equipment_master.json to know which attributes are
   checkable, it also knows the CANONICAL unit compliance-service expects,
   and substitutes it in -- this doesn't launder a genuine unit error (Amps
   submitted where kA is required), it corrects a label-phrasing mismatch
   for a value already extracted from a sentence in the correct physical
   unit under an attribute name that already implies that unit.

3. ENUM SPLIT mismatch: extraction-service's units.py deliberately splits a
   numeric-prefixed value+unit string apart (e.g. "7.0%" -> value=7.0,
   unit="%") -- correct and necessary for RANGE-type attributes like
   impedance. But an ENUM-type attribute like input_voltage ("480V") also
   has a numeric prefix, gets the same split (value=480, unit="V"), and
   compliance-service's ENUM check does an exact string comparison against
   "480V" -- str(480) != "480V", a guaranteed FAIL on a real live run (real
   bug: PDU-01 came back FAIL, gold says PASS). extraction-service has no
   way to know which attributes are ENUM-checked (that's compliance-service-
   internal, spec_data.py's _ENUM_ATTRIBUTES set) so it can't avoid this
   itself. The gateway recombines value+unit back into one string for
   attributes it can tell are ENUM-checked from equipment_master.json's own
   shape: a RANGE check always has acceptable_range_low and/or
   acceptable_range_high set (even a minimum-only check like SCCR
   withstand); an ENUM check has both null, by the dataset's own schema_note.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent.parent.parent.parent / "dataset" / "submittals" / "equipment_master.json"
EQUIPMENT_MASTER_PATH = Path(os.environ.get("EQUIPMENT_MASTER_PATH", DEFAULT_PATH))

_cache: dict | None = None


def _load() -> dict:
    """Returns {equipment_id: {"description": str, "attributes": {attribute: {"unit": ..., "is_enum": bool}}}}."""
    global _cache
    if _cache is not None:
        return _cache
    data = json.loads(EQUIPMENT_MASTER_PATH.read_text())
    result = {}
    for item in data["equipment"]:
        attrs = {}
        for a in item["attributes"]:
            is_enum = a["tolerance_pct"] is None and a["acceptable_range_low"] is None and a["acceptable_range_high"] is None
            attrs[a["attribute"]] = {"unit": a["unit"], "is_enum": is_enum}
        result[item["equipment_id"]] = {"description": item["description"], "attributes": attrs}
    _cache = result
    return result


def is_known_equipment(equipment_id: str) -> bool:
    return equipment_id in _load()


def equipment_description(equipment_id: str) -> str:
    return _load().get(equipment_id, {}).get("description", equipment_id)


def _maybe_recombine_enum_value(value, unit) -> object:
    """Undo extraction-service's numeric+unit split for ENUM attributes
    (e.g. value=480, unit='V' -> '480V') so the recombined string can match
    compliance-service's exact-string ENUM comparison against
    required_value. Only applies when value is numeric and there's a unit
    to recombine; a genuinely non-numeric enum value (e.g. "R-410A") was
    never split in the first place and passes through unchanged."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if not unit:
        return value
    combined = f"{value}{unit}"
    return combined


def filter_checkable_attributes(equipment_id: str, extracted_attributes: list[dict]) -> tuple[list[dict], list[str], list[str]]:
    """Returns (checkable, skipped_attribute_names, notes).

    `checkable` entries keep only the {attribute, value, unit} fields
    compliance-service's ExtractedAttribute schema accepts, with `unit`
    overridden to the canonical spec unit and ENUM values recombined where
    applicable (see module docstring for why both are necessary, not just
    convenient).

    If extraction returns more than one entry for the same attribute name
    (a real, observed failure mode: prose mentioning a sibling equipment's
    or the spec minimum's value under the same attribute name got extracted
    as extra "readings" of GEN-02's own rating, dragging a PASS to FAIL on
    an unrelated number) only the highest-confidence entry is forwarded to
    compliance-service -- one attribute name must mean one submitted value,
    never several silently averaged into a rollup. The rest are dropped
    with a note, not silently discarded."""
    known = _load().get(equipment_id, {}).get("attributes", {})
    by_attr: dict[str, list[dict]] = {}
    for a in extracted_attributes:
        by_attr.setdefault(a["attribute"], []).append(a)

    checkable = []
    skipped = []
    notes = []
    for attr_name, entries in by_attr.items():
        if attr_name not in known:
            skipped.append(attr_name)
            continue

        if len(entries) > 1:
            entries = sorted(entries, key=lambda e: e.get("confidence", 0), reverse=True)
            notes.append(
                f"{attr_name}: {len(entries)} distinct values extracted for one attribute "
                f"({[e['value'] for e in entries]}) -- kept highest-confidence {entries[0]['value']!r}, dropped rest"
            )
        chosen = entries[0]

        canonical_unit = known[attr_name]["unit"]
        is_enum = known[attr_name]["is_enum"]
        extracted_unit = chosen["unit"]
        value = chosen["value"]

        if canonical_unit and (extracted_unit or "").strip().lower() != canonical_unit.strip().lower():
            notes.append(f"{attr_name}: unit label normalized {extracted_unit!r} -> {canonical_unit!r}")

        if is_enum:
            value = _maybe_recombine_enum_value(value, extracted_unit)

        checkable.append({"attribute": attr_name, "value": value, "unit": canonical_unit or extracted_unit})

    return checkable, skipped, notes
