"""Pydantic request/response schemas matching the contract in README.md."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PropagateRequest(BaseModel):
    equipment_id: str
    resubmit_delay_days: int = Field(ge=0)
    # Not required by the documented contract (defaults to the IST
    # milestone, matching the README's example) -- exposed as an optional
    # override rather than hardcoded so other commissioning milestones can
    # be queried without changing the contract for existing callers.
    milestone_activity_id: str = "CX-L5-IST"


class AffectedActivity(BaseModel):
    activity_id: str
    activity_name: str
    baseline_early_finish: int
    new_early_finish: int
    baseline_total_float: int
    new_total_float: int


class MilestoneImpact(BaseModel):
    activity_id: str
    activity_name: str
    baseline_early_finish: int
    new_early_finish: int
    slip_days: int
    critical: bool


class PropagateResponse(BaseModel):
    triggering_activity: str
    milestone_impact: MilestoneImpact
    affected_activities: list[AffectedActivity]
    urgency: str
