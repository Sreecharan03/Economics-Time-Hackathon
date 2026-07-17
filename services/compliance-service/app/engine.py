"""
Deterministic compliance comparison engine. No LLM call anywhere in this file,
ever -- see the service README for why. This module is pure functions over
plain data; it does not touch the network, the filesystem, or a database.

Two check types cover every case in dataset/gold_set/compliance_gold_set.csv:
  - RANGE: numeric comparison against an inclusive [low, high] band, where
    either bound may be absent (a minimum-only check like switchgear
    withstand rating is just a RANGE with high=None; a tolerance-band check
    like transformer impedance is a RANGE with both bounds set). Unifying
    these into one code path means there is exactly one place a boundary
    bug could hide, not two.
  - ENUM: exact string match after trim (e.g. refrigerant type, voltage).

A SpecRequirement with conflicting_clauses set always yields CONFLICT,
checked before either comparison path -- the platform never silently picks
a side when the spec contradicts itself (see ATS-01 in the dataset).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class CheckType(str, Enum):
    RANGE = "range"
    ENUM = "enum"


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    CONFLICT = "CONFLICT"


class ComplianceEngineError(ValueError):
    """Malformed input. Raised, never swallowed into a guessed verdict."""


@dataclass(frozen=True)
class ConflictingClause:
    clause: str
    required_value: object
    unit: str | None = None


@dataclass(frozen=True)
class SpecRequirement:
    attribute: str
    spec_clause: str
    check_type: CheckType
    unit: str | None = None
    required_value: object | None = None
    acceptable_range_low: float | None = None
    acceptable_range_high: float | None = None
    conflicting_clauses: tuple[ConflictingClause, ...] | None = None


@dataclass(frozen=True)
class ComplianceResult:
    attribute: str
    submitted_value: object
    verdict: Verdict
    spec_clause: str
    required_value: object | None
    acceptable_range_low: float | None
    acceptable_range_high: float | None
    rationale: str


def _coerce_numeric(value: object) -> float:
    # bool is a subclass of int in Python -- isinstance(True, int) is True --
    # so this must be checked before the int/float branch or `True` would
    # silently coerce to 1.0 and pass a numeric range check it has no
    # business being compared against.
    if isinstance(value, bool):
        raise ComplianceEngineError(f"boolean is not a valid numeric submitted_value: {value!r}")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ComplianceEngineError("empty string is not a valid numeric submitted_value")
        try:
            result = float(stripped)
        except ValueError as e:
            raise ComplianceEngineError(f"cannot parse {value!r} as a number") from e
    else:
        raise ComplianceEngineError(f"unsupported type for numeric check: {type(value).__name__}")
    if math.isnan(result):
        raise ComplianceEngineError("submitted_value is NaN, not a valid measurement")
    if math.isinf(result):
        raise ComplianceEngineError("submitted_value is infinite, not a valid measurement")
    return result


def check_compliance(
    submitted_value: object,
    requirement: SpecRequirement,
    submitted_unit: str | None = None,
) -> ComplianceResult:
    if submitted_unit is not None and requirement.unit is not None:
        if submitted_unit.strip().lower() != requirement.unit.strip().lower():
            raise ComplianceEngineError(
                f"unit mismatch for {requirement.attribute}: submitted "
                f"{submitted_unit!r} vs spec requires {requirement.unit!r} "
                f"-- refusing to compare values in different units"
            )

    if requirement.conflicting_clauses:
        clause_desc = "; ".join(
            f"{c.clause} requires {c.required_value}{' ' + c.unit if c.unit else ''}"
            for c in requirement.conflicting_clauses
        )
        return ComplianceResult(
            attribute=requirement.attribute,
            submitted_value=submitted_value,
            verdict=Verdict.CONFLICT,
            spec_clause=requirement.spec_clause,
            required_value=None,
            acceptable_range_low=None,
            acceptable_range_high=None,
            rationale=f"Spec contains conflicting requirements for {requirement.attribute}: {clause_desc}. "
                      f"Not auto-resolved -- surfaced for human/RFI review.",
        )

    if requirement.check_type == CheckType.ENUM:
        if submitted_value is None:
            raise ComplianceEngineError(f"submitted_value is None for enum check on {requirement.attribute}")
        submitted_norm = str(submitted_value).strip()
        required_norm = str(requirement.required_value).strip()
        verdict = Verdict.PASS if submitted_norm == required_norm else Verdict.FAIL
        return ComplianceResult(
            attribute=requirement.attribute,
            submitted_value=submitted_value,
            verdict=verdict,
            spec_clause=requirement.spec_clause,
            required_value=requirement.required_value,
            acceptable_range_low=None,
            acceptable_range_high=None,
            rationale=(
                f"Submitted {submitted_norm!r} matches required {required_norm!r}."
                if verdict == Verdict.PASS
                else f"Submitted {submitted_norm!r} does not match required {required_norm!r}."
            ),
        )

    if requirement.check_type == CheckType.RANGE:
        value = _coerce_numeric(submitted_value)
        low, high = requirement.acceptable_range_low, requirement.acceptable_range_high
        if low is None and high is None:
            raise ComplianceEngineError(f"RANGE check for {requirement.attribute} has neither bound defined")
        ok = True
        if low is not None:
            ok = ok and value >= low
        if high is not None:
            ok = ok and value <= high
        verdict = Verdict.PASS if ok else Verdict.FAIL
        range_desc = f"[{low if low is not None else '-inf'}, {high if high is not None else '+inf'}]"
        return ComplianceResult(
            attribute=requirement.attribute,
            submitted_value=submitted_value,
            verdict=verdict,
            spec_clause=requirement.spec_clause,
            required_value=requirement.required_value,
            acceptable_range_low=low,
            acceptable_range_high=high,
            rationale=(
                f"Submitted {value} is within acceptable range {range_desc}."
                if verdict == Verdict.PASS
                else f"Submitted {value} is outside acceptable range {range_desc}."
            ),
        )

    raise ComplianceEngineError(f"unknown check_type: {requirement.check_type!r}")


def rollup_verdict(verdicts: list[Verdict]) -> Verdict:
    """Equipment-level verdict from its per-attribute verdicts: FAIL beats
    CONFLICT beats PASS. Mirrors dataset/submittals/equipment_master.json's
    rollup rule exactly -- see check_dataset_integrity.py's rollup check."""
    if not verdicts:
        raise ComplianceEngineError("cannot roll up an empty verdict list")
    if Verdict.FAIL in verdicts:
        return Verdict.FAIL
    if Verdict.CONFLICT in verdicts:
        return Verdict.CONFLICT
    return Verdict.PASS
