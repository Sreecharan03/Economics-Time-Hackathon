"""Pydantic request/response schemas matching the contract in README.md."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SimilarRfisRequest(BaseModel):
    query_text: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=20)


class RfiMatch(BaseModel):
    rfi_id: str
    source_project: str | None
    subject: str
    score: float
    resolution: str | None


class SimilarRfisResponse(BaseModel):
    results: list[RfiMatch]
