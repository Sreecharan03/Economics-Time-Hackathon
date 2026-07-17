"""Pydantic request/response schemas matching the contract in README.md."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedAttribute(BaseModel):
    attribute: str
    value: float | int | str
    unit: str | None = None


class ComplianceCheckRequest(BaseModel):
    equipment_id: str
    extracted_attributes: list[ExtractedAttribute] = Field(min_length=1)


class AttributeResult(BaseModel):
    attribute: str
    submitted_value: float | int | str
    required_value: float | int | str | None
    tolerance_pct: float | None = None
    acceptable_range: tuple[float | None, float | None] | None = None
    unit: str | None
    verdict: str
    spec_section: str
    rationale: str
    conflicting_clauses: list[dict] | None = None


class ComplianceCheckResponse(BaseModel):
    equipment_id: str
    overall_verdict: str
    results: list[AttributeResult]
