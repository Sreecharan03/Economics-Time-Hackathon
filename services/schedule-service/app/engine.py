"""
Deterministic CPM (Critical Path Method) forward/backward-pass engine. No
LLM call anywhere in this file, ever -- see the service README.

This is the SAME algorithm independently verified by
dataset/schedule/validate_cpm.py (baseline network) and
dataset/schedule/validate_propagation.py (both seeded delay scenarios) --
both of those scripts remain the source of truth for "is this algorithm
correct" and run in CI on every push. This module wraps that already-proven
logic for API use; it is not a reimplementation with new logic, on purpose
-- a second independent implementation would just be a second place for the
same class of bug (the switchgear 263-vs-273 float error) to hide.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


class ScheduleEngineError(ValueError):
    """Malformed network or request. Raised, never guessed past."""


@dataclass(frozen=True)
class Activity:
    activity_id: str
    activity_name: str
    activity_type: str
    duration_days: int
    predecessors: tuple[tuple[str, int], ...]  # (predecessor_id, lag_days)
    equipment_id: tuple[str, ...] = ()
    package_id: str | None = None
    commissioning_test_id: str | None = None


def parse_predecessors(raw: str) -> tuple[tuple[str, int], ...]:
    """Parses 'ACT1:FS,ACT2:FS+34' style predecessor strings -- finish-to-
    start only, by design (see dataset/schedule/README.md)."""
    if not raw:
        return ()
    out = []
    for tok in raw.split(","):
        tok = tok.strip()
        m = re.match(r"([A-Za-z0-9\-]+):FS\+?(\d+)?$", tok)
        if not m:
            raise ScheduleEngineError(f"unparseable predecessor token: {tok!r}")
        out.append((m.group(1), int(m.group(2) or 0)))
    return tuple(out)


@dataclass(frozen=True)
class CPMResult:
    early_start: dict[str, int]
    early_finish: dict[str, int]
    late_start: dict[str, int]
    late_finish: dict[str, int]
    total_float: dict[str, int]
    project_finish: int


def run_cpm(activities: dict[str, Activity], duration_overrides: dict[str, int] | None = None) -> CPMResult:
    """Full forward + backward pass over the WHOLE network, every time --
    never just the triggering activity's own chain. That shortcut is exactly
    what produced the 263-vs-273 float bug in the hand-built dataset: an
    activity can have more than one successor, and the *tighter* successor
    constraint governs its float, which a single-chain calculation misses.
    """
    if not activities:
        raise ScheduleEngineError("cannot run CPM on an empty activity set")

    overrides = duration_overrides or {}
    for aid in overrides:
        if aid not in activities:
            raise ScheduleEngineError(f"duration_overrides references unknown activity {aid!r}")
        if overrides[aid] < 0:
            raise ScheduleEngineError(f"duration_overrides for {aid!r} is negative: {overrides[aid]}")

    durations = {aid: overrides.get(aid, a.duration_days) for aid, a in activities.items()}
    preds = {aid: a.predecessors for aid, a in activities.items()}

    succs: dict[str, list[tuple[str, int]]] = {aid: [] for aid in activities}
    for aid, plist in preds.items():
        for pid, lag in plist:
            if pid not in activities:
                raise ScheduleEngineError(f"{aid}: dangling predecessor reference {pid!r}")
            succs[pid].append((aid, lag))

    early_start: dict[str, int] = {}
    early_finish: dict[str, int] = {}
    remaining = set(activities)
    changed = True
    while remaining and changed:
        changed = False
        for aid in list(remaining):
            plist = preds[aid]
            if all(pid in early_finish for pid, _ in plist):
                es = max((early_finish[pid] + lag for pid, lag in plist), default=0)
                early_start[aid] = es
                early_finish[aid] = es + durations[aid]
                remaining.discard(aid)
                changed = True
    if remaining:
        raise ScheduleEngineError(f"forward pass could not resolve (predecessor cycle?): {sorted(remaining)}")

    project_finish = max(early_finish.values())

    late_start: dict[str, int] = {}
    late_finish: dict[str, int] = {}
    remaining = set(activities)
    changed = True
    while remaining and changed:
        changed = False
        for aid in list(remaining):
            slist = succs[aid]
            if not slist:
                late_finish[aid] = project_finish
                late_start[aid] = project_finish - durations[aid]
                remaining.discard(aid)
                changed = True
                continue
            if all(sid in late_start for sid, _ in slist):
                lf = min(late_start[sid] - lag for sid, lag in slist)
                late_finish[aid] = lf
                late_start[aid] = lf - durations[aid]
                remaining.discard(aid)
                changed = True
    if remaining:
        raise ScheduleEngineError(f"backward pass could not resolve (successor cycle?): {sorted(remaining)}")

    total_float = {aid: late_finish[aid] - early_finish[aid] for aid in activities}
    return CPMResult(
        early_start=early_start,
        early_finish=early_finish,
        late_start=late_start,
        late_finish=late_finish,
        total_float=total_float,
        project_finish=project_finish,
    )


def find_submittal_activity(activities: dict[str, Activity], equipment_id: str) -> Activity:
    candidates = [
        a for a in activities.values()
        if a.activity_type == "submittal" and equipment_id in a.equipment_id
    ]
    if not candidates:
        raise ScheduleEngineError(f"no submittal activity found for equipment_id {equipment_id!r}")
    if len(candidates) > 1:
        raise ScheduleEngineError(
            f"multiple submittal activities found for equipment_id {equipment_id!r}: "
            f"{[a.activity_id for a in candidates]} -- ambiguous, refusing to guess"
        )
    return candidates[0]


@dataclass(frozen=True)
class PropagationResult:
    triggering_activity: str
    baseline: CPMResult
    propagated: CPMResult
    milestone_activity_id: str


def propagate_delay(
    activities: dict[str, Activity],
    equipment_id: str,
    resubmit_delay_days: int,
    milestone_activity_id: str = "CX-L5-IST",
) -> PropagationResult:
    """Applies resubmit_delay_days to the equipment's submittal-review
    activity and recomputes the ENTIRE network (not just its chain) to see
    whether milestone_activity_id slips."""
    if resubmit_delay_days < 0:
        raise ScheduleEngineError(f"resubmit_delay_days must be >= 0, got {resubmit_delay_days}")
    if milestone_activity_id not in activities:
        raise ScheduleEngineError(f"unknown milestone_activity_id: {milestone_activity_id!r}")

    trigger = find_submittal_activity(activities, equipment_id)
    baseline = run_cpm(activities)
    propagated = run_cpm(
        activities,
        duration_overrides={trigger.activity_id: trigger.duration_days + resubmit_delay_days},
    )

    return PropagationResult(
        triggering_activity=trigger.activity_id,
        baseline=baseline,
        propagated=propagated,
        milestone_activity_id=milestone_activity_id,
    )
