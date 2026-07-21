"""Pydantic request/response schemas matching the contract in README.md."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    # Required at the gateway level even though extraction-service itself
    # treats this as an optional hint -- compliance-service requires a known
    # equipment_id to look up spec requirements, so without it nothing
    # downstream of extraction can run. Tightening the contract here (vs.
    # extraction-service's own Optional) is a deliberate gateway-level choice.
    equipment_id_hint: str = Field(min_length=1)
    raw_submittal_text: str = Field(min_length=1)
    spec_section_hint: str | None = None


class ReviewResponse(BaseModel):
    equipment_id: str
    extraction: dict
    compliance: dict | None
    schedule: dict | None
    precedent: list[dict] = Field(default_factory=list)
    draft_rfi: dict | None
    requires_human_approval: bool = True
    pipeline_warnings: list[str] = Field(default_factory=list)
