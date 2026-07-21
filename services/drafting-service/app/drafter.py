"""
Orchestrates one drafting call: assemble grounded context from the request
payload (already-decided facts from compliance-service/schedule-service/
retrieval-service -- this service invents nothing), call the (injectable)
LLM, parse its JSON, and deterministically validate that every citation the
model claims actually resolves to something present in the input payload.
That validation is the actual guardrail -- not the system prompt's wording,
which the model can and does drift from.
"""
from __future__ import annotations

import json
import re

from app.llm_client import call_groq
from app.models import Citation, DraftRfiBody, DraftRfiRequest

SYSTEM_PROMPT = """You draft a construction RFI (Request for Information) grounded ONLY in the \
evidence provided in the user message -- a JSON payload of already-decided compliance and \
schedule facts. Do not invent facts, values, or spec clauses not present in the payload.

Return ONLY valid JSON matching this schema:
{"subject": "<one-line subject>", "body": "<full RFI text, under 200 words>", \
"citations": [{"type": "spec_clause|submittal|schedule_activity|precedent_rfi", "ref": "<exact id from the payload>"}]}

Rules:
- Cite the specific spec_section from compliance_result.results for every FAIL/CONFLICT attribute discussed.
- If schedule_result is present, state its urgency and slip_days plainly (critical vs flagged-not-critical).
- If precedent entries are present, reference at least one by rfi_id.
- Every citation.ref MUST be an id that appears verbatim in the payload (a spec_section string, \
the equipment_id, a schedule activity_id, or a precedent rfi_id) -- never invent one.
- End with a clear requested action, and state explicitly that human engineer sign-off is \
required before any status change -- this is advisory, not an approval."""


class DraftingError(ValueError):
    pass


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def parse_llm_json(raw_response: str) -> dict:
    text = raw_response.strip()
    fence_match = _JSON_FENCE_RE.search(text)
    candidate = fence_match.group(1) if fence_match else text
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as e:
        raise DraftingError(f"LLM response was not valid JSON: {e}") from e
    for key in ("subject", "body", "citations"):
        if key not in parsed:
            raise DraftingError(f"LLM response JSON missing required key '{key}'")
    if not isinstance(parsed["citations"], list):
        raise DraftingError("'citations' must be a list")
    return parsed


def collect_valid_refs(req: DraftRfiRequest) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {
        "spec_clause": {r.spec_section for r in req.compliance_result.results},
        "submittal": {req.equipment_id},
        "schedule_activity": set(),
        "precedent_rfi": {p.rfi_id for p in req.precedent},
    }
    if req.schedule_result is not None:
        refs["schedule_activity"] |= {
            req.schedule_result.triggering_activity,
            req.schedule_result.milestone_impact.activity_id,
        }
    return refs


def validate_citations(raw_citations: list[dict], valid_refs: dict[str, set[str]]) -> tuple[list[Citation], list[str]]:
    kept: list[Citation] = []
    warnings: list[str] = []
    for c in raw_citations:
        ctype, ref = c.get("type"), c.get("ref")
        if ctype is None or ref is None:
            warnings.append(f"citation missing type/ref, dropped: {c}")
            continue
        allowed = valid_refs.get(ctype, set())
        if ref not in allowed:
            warnings.append(f"citation ({ctype}, {ref!r}) does not resolve to any field in the request payload, dropped")
            continue
        kept.append(Citation(type=ctype, ref=ref))
    return kept, warnings


def draft_rfi(req: DraftRfiRequest, llm_fn=call_groq) -> tuple[DraftRfiBody, list[str]]:
    user_payload = json.dumps(
        {
            "equipment_id": req.equipment_id,
            "compliance_result": req.compliance_result.model_dump(),
            "schedule_result": req.schedule_result.model_dump() if req.schedule_result else None,
            "precedent": [p.model_dump() for p in req.precedent],
        },
        indent=2,
    )
    raw_response = llm_fn(SYSTEM_PROMPT, user_payload)
    parsed = parse_llm_json(raw_response)

    valid_refs = collect_valid_refs(req)
    citations, warnings = validate_citations(parsed["citations"], valid_refs)

    body = DraftRfiBody(subject=parsed["subject"], body=parsed["body"], citations=citations)
    return body, warnings
