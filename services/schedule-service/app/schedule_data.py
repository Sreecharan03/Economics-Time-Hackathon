"""
Loads the baseline CPM network from dataset/schedule/schedule.csv. Same
seed-data pattern as compliance-service/app/spec_data.py, including the same
lazy-evaluation discipline for the env var override: the relative-path
default is only computed when SCHEDULE_CSV_PATH is actually unset, never
passed as os.environ.get()'s default argument (which Python evaluates
eagerly regardless of whether the env var is present). That exact mistake
crashed compliance-service's container on its first real run; not repeating
it here.
"""
from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path

from app.engine import Activity, parse_predecessors


def _default_schedule_path() -> Path:
    # services/schedule-service/app/schedule_data.py -> repo root is 3
    # levels up. Only holds when the full repo is checked out (pytest);
    # inside a Docker build (context = just this service dir) there is no
    # repo root to walk up to, hence the env var override in the Dockerfile.
    return Path(__file__).resolve().parents[3] / "dataset" / "schedule" / "schedule.csv"


_env_path = os.environ.get("SCHEDULE_CSV_PATH")
_SCHEDULE_PATH = Path(_env_path) if _env_path else _default_schedule_path()


@lru_cache(maxsize=1)
def load_activities(path: Path | None = None) -> dict[str, Activity]:
    source = path or _SCHEDULE_PATH
    with open(source) as f:
        rows = list(csv.DictReader(f))

    activities: dict[str, Activity] = {}
    for r in rows:
        equipment_ids = tuple(t.strip() for t in r["equipment_id"].split(",")) if r["equipment_id"] else ()
        activities[r["activity_id"]] = Activity(
            activity_id=r["activity_id"],
            activity_name=r["activity_name"],
            activity_type=r["activity_type"],
            duration_days=int(r["duration_days"]),
            predecessors=parse_predecessors(r["predecessors"]),
            equipment_id=equipment_ids,
            package_id=r["package_id"] or None,
            commissioning_test_id=r["commissioning_test_id"] or None,
        )
    return activities
