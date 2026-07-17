"""
FastAPI wrapper around the deterministic CPM engine. No CPM logic lives
here -- this only validates the request, calls propagate_delay, and shapes
the response per README.md's contract. See engine.py for the algorithm.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.engine import ScheduleEngineError, propagate_delay
from app.models import AffectedActivity, MilestoneImpact, PropagateRequest, PropagateResponse
from app.schedule_data import load_activities

app = FastAPI(title="schedule-service")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/schedule/propagate", response_model=PropagateResponse)
def schedule_propagate(req: PropagateRequest) -> PropagateResponse:
    activities = load_activities()
    try:
        result = propagate_delay(
            activities, req.equipment_id, req.resubmit_delay_days, req.milestone_activity_id
        )
    except ScheduleEngineError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    mid = result.milestone_activity_id
    baseline_ef = result.baseline.early_finish[mid]
    new_ef = result.propagated.early_finish[mid]
    slip = new_ef - baseline_ef

    milestone_impact = MilestoneImpact(
        activity_id=mid,
        activity_name=activities[mid].activity_name,
        baseline_early_finish=baseline_ef,
        new_early_finish=new_ef,
        slip_days=slip,
        critical=slip > 0,
    )

    affected = [
        AffectedActivity(
            activity_id=aid,
            activity_name=activities[aid].activity_name,
            baseline_early_finish=result.baseline.early_finish[aid],
            new_early_finish=result.propagated.early_finish[aid],
            baseline_total_float=result.baseline.total_float[aid],
            new_total_float=result.propagated.total_float[aid],
        )
        for aid in activities
        if (
            result.baseline.early_finish[aid] != result.propagated.early_finish[aid]
            or result.baseline.total_float[aid] != result.propagated.total_float[aid]
        )
    ]
    affected.sort(key=lambda a: a.baseline_early_finish)

    return PropagateResponse(
        triggering_activity=result.triggering_activity,
        milestone_impact=milestone_impact,
        affected_activities=affected,
        urgency="CRITICAL" if milestone_impact.critical else "FLAGGED",
    )
