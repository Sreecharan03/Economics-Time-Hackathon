"""
Seed spec-requirement data. Loads from dataset/submittals/equipment_master.json
rather than hand-retyping the thresholds a second time -- that file's
required_value/tolerance_pct/acceptable_range_low/acceptable_range_high/
conflicting_clauses fields are exactly the requirement side of the data
(already independently validated by evals/check_dataset_integrity.py), and
duplicating them here by hand would just reintroduce the drift risk the gold-
set audit specifically fixed.

This is a stand-in for what will eventually be a `spec_requirement` Postgres
table (see infra/db/migrations/001_initial_schema.sql) seeded once at project
setup. Swapping this module for a DB-backed loader later should not require
changing engine.py or main.py's call sites -- both only depend on getting
back a SpecRequirement, not on where it came from.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from app.engine import CheckType, ConflictingClause, SpecRequirement

def _default_equipment_master_path() -> Path:
    # services/compliance-service/app/spec_data.py -> repo root is 3 levels
    # up, so this resolves correctly when the full repo is checked out
    # (which pytest always runs against). This assumption does NOT hold
    # inside a Docker build, where the build context is just
    # services/compliance-service/ and there is no repo root to walk up to
    # -- parents[3] would raise IndexError there. Must stay lazy (only
    # called when EQUIPMENT_MASTER_PATH is unset) rather than passed as
    # os.environ.get()'s default argument, which Python evaluates eagerly
    # regardless of whether the env var is present -- that eager-evaluation
    # mistake is exactly what crashed the container on first real run.
    return Path(__file__).resolve().parents[3] / "dataset" / "submittals" / "equipment_master.json"


_env_path = os.environ.get("EQUIPMENT_MASTER_PATH")
_EQUIPMENT_MASTER_PATH = Path(_env_path) if _env_path else _default_equipment_master_path()

_ENUM_ATTRIBUTES = {"refrigerant", "input_voltage"}


def _check_type_for(attribute: str) -> CheckType:
    return CheckType.ENUM if attribute in _ENUM_ATTRIBUTES else CheckType.RANGE


@lru_cache(maxsize=1)
def load_spec_requirements(path: Path | None = None) -> dict[str, dict[str, SpecRequirement]]:
    """Returns {equipment_id: {attribute: SpecRequirement}}."""
    source = path or _EQUIPMENT_MASTER_PATH
    with open(source) as f:
        data = json.load(f)

    result: dict[str, dict[str, SpecRequirement]] = {}
    for equip in data["equipment"]:
        attrs: dict[str, SpecRequirement] = {}
        for a in equip["attributes"]:
            conflicting = None
            if a.get("conflicting_clauses"):
                conflicting = tuple(
                    ConflictingClause(
                        clause=c["clause"],
                        required_value=c["required_value"],
                        unit=c.get("unit"),
                    )
                    for c in a["conflicting_clauses"]
                )
            attrs[a["attribute"]] = SpecRequirement(
                attribute=a["attribute"],
                spec_clause=a["spec_clause"],
                check_type=_check_type_for(a["attribute"]),
                unit=a.get("unit"),
                required_value=a.get("required_value"),
                acceptable_range_low=a.get("acceptable_range_low"),
                acceptable_range_high=a.get("acceptable_range_high"),
                conflicting_clauses=conflicting,
            )
        result[equip["equipment_id"]] = attrs
    return result


def get_requirement(equipment_id: str, attribute: str) -> SpecRequirement:
    reqs = load_spec_requirements()
    if equipment_id not in reqs:
        raise KeyError(f"no spec requirements seeded for equipment_id {equipment_id!r}")
    if attribute not in reqs[equipment_id]:
        raise KeyError(f"no spec requirement for attribute {attribute!r} on equipment {equipment_id!r}")
    return reqs[equipment_id][attribute]
