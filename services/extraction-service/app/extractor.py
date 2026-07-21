"""
Orchestrates one extraction call: build the prompt, call the (injectable)
LLM function, parse its JSON, deterministically verify each source_span
against the raw text (this is the actual anti-hallucination check -- not the
model's own say-so), normalize units, and shape the response.

`llm_fn` is injected so tests can exercise every branch of this logic
(malformed JSON, missing fields, hallucinated source_span, empty result...)
without a real network call for each case -- see tests/test_extractor.py.
Only a handful of marked integration tests in tests/test_live_groq.py call
the real Groq API, against the dataset's actual submittal files.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.llm_client import call_groq
from app.spec_vocabulary import vocabulary_for_section
from app.units import normalize_attribute, normalize_whitespace

EXTRACTION_SYSTEM_PROMPT_TEMPLATE = """You extract structured equipment attributes from raw \
construction submittal/cut-sheet text. Return ONLY valid JSON matching this schema:
{{"attributes": [{{"attribute": "<snake_case_name>", "value": <number or string>, \
"unit": "<unit or null>", "source_span": "<verbatim quote from the text supporting this value>"}}]}}

Rules:
- Extract every numeric or enum specification value a spec-compliance reviewer would need.
- Do not invent values that are not literally present in the text.
- `source_span` MUST be an exact, verbatim substring of the input text -- do not paraphrase it.
- Do not compute pass/fail or judge compliance -- a separate engine does that, not you.
{vocabulary_hint}"""


class ExtractionError(ValueError):
    pass


@dataclass
class ExtractedAttribute:
    attribute: str
    value: float | int | str
    unit: str | None
    source_span: str
    confidence: float


def build_system_prompt(spec_section_hint: str | None) -> str:
    vocab = vocabulary_for_section(spec_section_hint)
    if vocab:
        lines = "\n".join(f'  - "{v["attribute"]}" (unit: {v["unit"]})' for v in vocab)
        hint = f"\nKnown attribute names for spec section {spec_section_hint}, prefer these exact names when applicable:\n{lines}"
    else:
        hint = ""
    return EXTRACTION_SYSTEM_PROMPT_TEMPLATE.format(vocabulary_hint=hint)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def parse_llm_json(raw_response: str) -> dict:
    text = raw_response.strip()
    fence_match = _JSON_FENCE_RE.search(text)
    candidate = fence_match.group(1) if fence_match else text
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"LLM response was not valid JSON: {e}") from e
    if not isinstance(parsed, dict) or "attributes" not in parsed:
        raise ExtractionError("LLM response JSON missing required 'attributes' key")
    if not isinstance(parsed["attributes"], list):
        raise ExtractionError("'attributes' must be a list")
    return parsed


def verify_source_span(source_span: str, raw_text: str) -> tuple[bool, bool]:
    """Returns (exact_match, case_insensitive_match)."""
    norm_span = normalize_whitespace(source_span)
    norm_text = normalize_whitespace(raw_text)
    exact = norm_span in norm_text
    fuzzy = exact or (norm_span.lower() in norm_text.lower())
    return exact, fuzzy


def confidence_for_span(exact: bool, fuzzy: bool) -> float:
    if exact:
        return 0.95
    if fuzzy:
        return 0.7
    return 0.3


def extract_from_text(
    raw_text: str,
    equipment_id_hint: str | None = None,
    spec_section_hint: str | None = None,
    llm_fn=call_groq,
) -> tuple[str | None, list[ExtractedAttribute], list[str]]:
    system_prompt = build_system_prompt(spec_section_hint)
    raw_response = llm_fn(system_prompt, raw_text)
    parsed = parse_llm_json(raw_response)

    results: list[ExtractedAttribute] = []
    warnings: list[str] = []

    for i, raw_attr in enumerate(parsed["attributes"]):
        missing = [k for k in ("attribute", "value", "source_span") if k not in raw_attr]
        if missing:
            warnings.append(f"attribute #{i} missing required field(s) {missing}, skipped")
            continue

        source_span = raw_attr["source_span"]
        exact, fuzzy = verify_source_span(source_span, raw_text)
        confidence = confidence_for_span(exact, fuzzy)
        if not exact and fuzzy:
            warnings.append(f"attribute '{raw_attr['attribute']}': source_span matched only case-insensitively")
        elif not fuzzy:
            warnings.append(
                f"attribute '{raw_attr['attribute']}': source_span not found verbatim in text -- possible hallucination risk"
            )

        value, unit = normalize_attribute(raw_attr["value"], raw_attr.get("unit"))

        results.append(
            ExtractedAttribute(
                attribute=raw_attr["attribute"],
                value=value,
                unit=unit,
                source_span=source_span,
                confidence=confidence,
            )
        )

    if not results:
        warnings.append("no attributes extracted from this document")

    return equipment_id_hint, results, warnings
