"""FastAPI wrapper. No orchestration logic of its own -- see orchestrator.py."""
from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException

from app.models import ReviewRequest, ReviewResponse
from app.orchestrator import GatewayError, review_submittal

app = FastAPI(title="gateway")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/review/submittal", response_model=ReviewResponse)
async def review(req: ReviewRequest) -> ReviewResponse:
    async with httpx.AsyncClient() as client:
        try:
            result = await review_submittal(client, req.equipment_id_hint, req.raw_submittal_text, req.spec_section_hint)
        except GatewayError as e:
            raise HTTPException(status_code=e.status_code, detail=e.message) from e
    return ReviewResponse(**result)
