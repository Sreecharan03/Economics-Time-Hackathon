"""
Pydantic request/response schemas matching the contract in README.md.

The three nested inputs (compliance_result, schedule_result, precedent) are
typed loosely (extra="allow") on purpose -- this service must not need to be
redeployed every time compliance-service or schedule-service adds a field.
Only the specific fields citation validation needs (spec_section, activity_id,
rfi_id) are declared; everything else passes through untouched into the LLM
prompt.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ComplianceAttributeResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    attribute: str
    submitted_value: float | int | str
    required_value: float | int | str | None = None
    unit: str | None = None
    verdict: str
    spec_section: str
    rationale: str


class ComplianceResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    equipment_id: str
    overall_verdict: str
    results: list[ComplianceAttributeResult]


class ScheduleMilestoneImpact(BaseModel):
    model_config = ConfigDict(extra="allow")
    activity_id: str
    activity_name: str
    slip_days: int
    critical: bool


class ScheduleResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    triggering_activity: str
    milestone_impact: ScheduleMilestoneImpact
    urgency: str


class PrecedentRfi(BaseModel):
    model_config = ConfigDict(extra="allow")
    rfi_id: str
    source_project: str | None = None
    resolution: str | None = None


class DraftRfiRequest(BaseModel):
    equipment_id: str
    compliance_result: ComplianceResult
    schedule_result: ScheduleResult | None = None
    precedent: list[PrecedentRfi] = Field(default_factory=list)


class Citation(BaseModel):
    type: str
    ref: str


class DraftRfiBody(BaseModel):
    subject: str
    body: str
    citations: list[Citation]


class DraftRfiResponse(BaseModel):
    draft_rfi: DraftRfiBody
    requires_human_approval: bool = True
    draft_warnings: list[str] = Field(default_factory=list)
