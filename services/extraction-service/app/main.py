"""
FastAPI wrapper. No extraction logic of its own -- see extractor.py for the
actual pipeline, llm_client.py for the Groq call.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.extractor import ExtractionError, extract_from_text
from app.llm_client import LLMNotConfigured, is_configured
from app.models import ExtractedAttributeOut, ExtractionRequest, ExtractionResponse

app = FastAPI(title="extraction-service")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_configured": is_configured()}


@app.post("/extraction/submittal", response_model=ExtractionResponse)
def extract_submittal(req: ExtractionRequest) -> ExtractionResponse:
    try:
        equipment_id, attrs, warnings = extract_from_text(
            req.raw_text, req.equipment_id_hint, req.spec_section_hint
        )
    except LLMNotConfigured as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except ExtractionError as e:
        raise HTTPException(status_code=502, detail=f"LLM returned unusable output: {e}") from e

    return ExtractionResponse(
        equipment_id=equipment_id,
        extracted_attributes=[
            ExtractedAttributeOut(
                attribute=a.attribute, value=a.value, unit=a.unit, source_span=a.source_span, confidence=a.confidence
            )
            for a in attrs
        ],
        extraction_warnings=warnings,
    )
