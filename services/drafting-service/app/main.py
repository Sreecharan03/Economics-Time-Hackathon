"""FastAPI wrapper. No drafting/citation logic of its own -- see drafter.py."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.drafter import DraftingError, draft_rfi
from app.llm_client import LLMNotConfigured, is_configured
from app.models import DraftRfiRequest, DraftRfiResponse

app = FastAPI(title="drafting-service")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_configured": is_configured()}


@app.post("/drafting/rfi", response_model=DraftRfiResponse)
def drafting_rfi(req: DraftRfiRequest) -> DraftRfiResponse:
    try:
        body, warnings = draft_rfi(req)
    except LLMNotConfigured as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except DraftingError as e:
        raise HTTPException(status_code=502, detail=f"LLM returned unusable output: {e}") from e

    return DraftRfiResponse(draft_rfi=body, requires_human_approval=True, draft_warnings=warnings)
