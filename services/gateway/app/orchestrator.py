"""
Owns the request lifecycle described in README.md's "Orchestration order for
one request". Contains no domain logic of its own -- every judgment call is
delegated to the five downstream services; this module only sequences calls,
maps between their schemas, and decides what's REQUIRED vs BEST-EFFORT:

- extraction-service, compliance-service: REQUIRED. Without a verdict there
  is nothing to orchestrate, so failures here abort the whole request.
- schedule-service, retrieval-service, drafting-service: BEST-EFFORT. A
  compliance verdict is still useful on its own; if any of these three is
  down or errors, the review degrades gracefully (null/empty field +
  pipeline_warnings entry) rather than failing the entire request.

The optional `on_stage` callback (async, takes one dict) lets a caller
observe real stage transitions as they happen -- used by main.py's SSE
endpoint to give the frontend a live progress view. It defaults to a no-op
so the plain `review_submittal` behavior (and all of test_orchestrator.py /
test_live_full_pipeline.py, none of which pass on_stage) is unchanged; this
is instrumentation, not a second code path to keep in sync.
"""
from __future__ import annotations

import asyncio

import httpx

from app import clients
from app.clients import ServiceHTTPError, ServiceUnavailable
from app.spec_filter import equipment_description, filter_checkable_attributes, is_known_equipment

# Plain-language stage names, not service names -- these are what the
# frontend shows a reviewer, who shouldn't need to know what
# "extraction-service" means. Order matches README.md's orchestration order.
STAGE_READING = "reading"
STAGE_CHECKING = "checking"
STAGE_CALENDAR = "calendar"
STAGE_MEMORY = "memory"
STAGE_WRITING = "writing"


class GatewayError(RuntimeError):
    """Fatal error -- the review cannot proceed at all."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


async def _emit(on_stage, stage: str, status: str, **extra) -> None:
    if on_stage is not None:
        await on_stage({"stage": stage, "status": status, **extra})


def _empty_result(equipment_id: str, extraction: dict, warnings: list[str]) -> dict:
    return {
        "equipment_id": equipment_id,
        "extraction": extraction,
        "compliance": None,
        "schedule": None,
        "precedent": [],
        "draft_rfi": None,
        "requires_human_approval": True,
        "pipeline_warnings": warnings,
    }


def build_retrieval_query(equipment_id: str, compliance_result: dict) -> str:
    """compliance-service's rationale text is deliberately generic/templated
    ("Submitted 7.0 is outside acceptable range [5.32, 6.18].") -- it has no
    domain words like "transformer" or "impedance" in it, which starves the
    embedding search of signal (real bug: this alone pulled a UPS breaker-
    rating RFI for a transformer-impedance deviation on first live run,
    RFI-HIST-001 instead of the actually-relevant RFI-HIST-003). Prepending
    the equipment description and attribute name -- both already available
    without another service call -- gives the query the same domain context
    a human reviewer would have."""
    non_pass = [r for r in compliance_result["results"] if r["verdict"] != "PASS"]
    if not non_pass:
        return ""
    parts = [equipment_description(equipment_id)]
    parts += [f"{r['attribute']}: {r['rationale']}" for r in non_pass if r.get("rationale")]
    return ". ".join(parts)


async def _safe_schedule(client: httpx.AsyncClient, equipment_id: str, warnings: list[str]) -> dict | None:
    try:
        return await clients.call_schedule(client, equipment_id)
    except ServiceHTTPError as e:
        if e.status_code == 404:
            warnings.append(f"schedule-service: no schedule activity linked to {equipment_id!r} -- schedule impact unknown")
        else:
            warnings.append(f"schedule-service error ({e.status_code}): {e.detail}")
        return None
    except ServiceUnavailable as e:
        warnings.append(f"schedule-service unavailable: {e.detail}")
        return None


async def _safe_retrieval(client: httpx.AsyncClient, query_text: str, warnings: list[str]) -> list[dict]:
    if not query_text:
        return []
    try:
        result = await clients.call_retrieval(client, query_text)
        return result["results"]
    except ServiceHTTPError as e:
        warnings.append(f"retrieval-service error ({e.status_code}): {e.detail}")
        return []
    except ServiceUnavailable as e:
        warnings.append(f"retrieval-service unavailable: {e.detail}")
        return []


async def _safe_drafting(
    client: httpx.AsyncClient,
    equipment_id: str,
    compliance: dict,
    schedule_result: dict | None,
    precedent: list[dict],
    warnings: list[str],
) -> dict | None:
    try:
        draft_response = await clients.call_drafting(client, equipment_id, compliance, schedule_result, precedent)
    except ServiceHTTPError as e:
        warnings.append(f"drafting-service error ({e.status_code}): {e.detail}")
        return None
    except ServiceUnavailable as e:
        warnings.append(f"drafting-service unavailable: {e.detail}")
        return None
    warnings.extend(draft_response.get("draft_warnings", []))
    return draft_response["draft_rfi"]


async def review_submittal(
    client: httpx.AsyncClient,
    equipment_id_hint: str,
    raw_submittal_text: str,
    spec_section_hint: str | None = None,
    on_stage=None,
) -> dict:
    warnings: list[str] = []

    # --- Step 1: extraction (REQUIRED) ---
    await _emit(on_stage, STAGE_READING, "started")
    try:
        extraction = await clients.call_extraction(client, equipment_id_hint, raw_submittal_text, spec_section_hint)
    except ServiceUnavailable as e:
        await _emit(on_stage, STAGE_READING, "error", detail=e.detail)
        raise GatewayError(503, f"extraction-service unavailable: {e.detail}") from e
    except ServiceHTTPError as e:
        await _emit(on_stage, STAGE_READING, "error", detail=e.detail)
        raise GatewayError(502, f"extraction-service error ({e.status_code}): {e.detail}") from e

    equipment_id = extraction.get("equipment_id") or equipment_id_hint
    await _emit(on_stage, STAGE_READING, "done", data=extraction)

    if not extraction["extracted_attributes"]:
        await _emit(on_stage, STAGE_CHECKING, "skipped", reason="no attributes extracted")
        return _empty_result(
            equipment_id,
            extraction,
            ["no attributes extracted from submittal text -- cannot assess compliance"] + extraction.get("extraction_warnings", []),
        )

    if not is_known_equipment(equipment_id):
        await _emit(on_stage, STAGE_CHECKING, "skipped", reason="equipment not recognized")
        return _empty_result(equipment_id, extraction, [f"equipment_id {equipment_id!r} not recognized -- no spec requirements on file"])

    checkable, skipped, unit_notes = filter_checkable_attributes(equipment_id, extraction["extracted_attributes"])
    if skipped:
        warnings.append(f"extracted but not spec-checked (informational, not a deviation): {skipped}")
    if unit_notes:
        warnings.append(f"unit labels normalized to match spec (informational): {unit_notes}")
    if not checkable:
        await _emit(on_stage, STAGE_CHECKING, "skipped", reason="no checkable attributes")
        return _empty_result(
            equipment_id,
            extraction,
            [f"extracted {len(extraction['extracted_attributes'])} attribute(s) but none match a checkable "
             f"spec requirement for {equipment_id!r}"] + warnings,
        )

    # --- Step 2: compliance (REQUIRED) ---
    await _emit(on_stage, STAGE_CHECKING, "started")
    try:
        compliance = await clients.call_compliance(client, equipment_id, checkable)
    except ServiceUnavailable as e:
        await _emit(on_stage, STAGE_CHECKING, "error", detail=e.detail)
        raise GatewayError(503, f"compliance-service unavailable: {e.detail}") from e
    except ServiceHTTPError as e:
        await _emit(on_stage, STAGE_CHECKING, "error", detail=e.detail)
        # compliance-service 404s on an unrecognized (equipment_id, attribute)
        # pair -- shouldn't happen given the filter above, but if the filter
        # and compliance-service's own seed data ever drift, surface it as a
        # gateway bug (502), not a client error.
        raise GatewayError(502, f"compliance-service error ({e.status_code}): {e.detail}") from e

    verdict = compliance["overall_verdict"]
    await _emit(on_stage, STAGE_CHECKING, "done", data=compliance)

    if verdict == "PASS":
        await _emit(on_stage, STAGE_CALENDAR, "skipped", reason="compliant, no further review needed")
        await _emit(on_stage, STAGE_MEMORY, "skipped", reason="compliant, no further review needed")
        await _emit(on_stage, STAGE_WRITING, "skipped", reason="compliant, no further review needed")
        return {
            "equipment_id": equipment_id,
            "extraction": extraction,
            "compliance": compliance,
            "schedule": None,
            "precedent": [],
            "draft_rfi": None,
            "requires_human_approval": True,
            "pipeline_warnings": warnings,
        }

    # --- Steps 3: schedule + retrieval, run concurrently (BEST-EFFORT) ---
    await _emit(on_stage, STAGE_CALENDAR, "started")
    await _emit(on_stage, STAGE_MEMORY, "started")
    query_text = build_retrieval_query(equipment_id, compliance)
    schedule_result, precedent = await asyncio.gather(
        _safe_schedule(client, equipment_id, warnings),
        _safe_retrieval(client, query_text, warnings),
    )
    await _emit(on_stage, STAGE_CALENDAR, "done", data=schedule_result)
    await _emit(on_stage, STAGE_MEMORY, "done", data=precedent)

    # --- Step 4: drafting (BEST-EFFORT) ---
    await _emit(on_stage, STAGE_WRITING, "started")
    draft_rfi = await _safe_drafting(client, equipment_id, compliance, schedule_result, precedent, warnings)
    await _emit(on_stage, STAGE_WRITING, "done", data=draft_rfi)

    return {
        "equipment_id": equipment_id,
        "extraction": extraction,
        "compliance": compliance,
        "schedule": schedule_result,
        "precedent": precedent,
        "draft_rfi": draft_rfi,
        "requires_human_approval": True,
        "pipeline_warnings": warnings,
    }
