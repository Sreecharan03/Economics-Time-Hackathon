"""FastAPI wrapper. No orchestration logic of its own -- see orchestrator.py."""
from __future__ import annotations

import asyncio
import json
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.models import ReviewRequest, ReviewResponse
from app.orchestrator import GatewayError, review_submittal

app = FastAPI(title="gateway")

# The frontend is a separate origin (its own dev server / container) --
# without this, every browser call would fail on CORS before ever reaching
# the orchestrator. Restricted to an explicit allowlist, not "*", since this
# API accepts POST with a JSON body (credentials aren't used, but origin
# should still be intentional, not wildcarded).
_allowed_origins = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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


@app.post("/review/submittal/stream")
async def review_stream(req: ReviewRequest) -> StreamingResponse:
    """
    Server-Sent Events version of /review/submittal for the frontend's live
    pipeline view. Each event is a real stage transition emitted by
    orchestrator.py's on_stage callback as it actually happens -- not a
    client-side animation guessing at timing. Ends with one "complete" event
    carrying the same payload /review/submittal returns, or one "failed"
    event carrying a GatewayError's status/message.
    """

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        async def on_stage(event: dict) -> None:
            await queue.put(event)

        async def run() -> None:
            async with httpx.AsyncClient() as client:
                try:
                    result = await review_submittal(
                        client, req.equipment_id_hint, req.raw_submittal_text, req.spec_section_hint, on_stage=on_stage
                    )
                    await queue.put({"stage": "complete", "status": "done", "data": result})
                except GatewayError as e:
                    await queue.put({"stage": "failed", "status": "error", "status_code": e.status_code, "detail": e.message})
            await queue.put(None)  # sentinel: stream done

        task = asyncio.create_task(run())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            await task

    return StreamingResponse(event_generator(), media_type="text/event-stream")
