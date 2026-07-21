"""Pydantic request/response schemas matching the contract in README.md."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    equipment_id_hint: str | None = None
    raw_text: str = Field(min_length=1)
    spec_section_hint: str | None = None


class ExtractedAttributeOut(BaseModel):
    attribute: str
    value: float | int | str
    unit: str | None
    source_span: str
    confidence: float


class ExtractionResponse(BaseModel):
    equipment_id: str | None
    extracted_attributes: list[ExtractedAttributeOut]
    extraction_warnings: list[str] = []
