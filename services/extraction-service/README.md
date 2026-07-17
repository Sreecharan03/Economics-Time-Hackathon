# extraction-service

## Responsibility

Turn a raw vendor submittal (PDF or plain text, e.g.
`dataset/submittals/XFMR-01_submittal.txt`) into a typed schema of
`{equipment_id, attribute, value, unit, source_span}` records. This is the one
step in the pipeline where an LLM call is doing real interpretive work
(reading unstructured vendor prose and pulling out the values that matter),
so it's also the step most likely to need a human-in-the-loop confirmation
step in the product UI before its output is trusted downstream.

## What it does NOT do

- Does not judge compliance (`compliance-service`'s job). This service's output
  is just extracted facts — it should never emit a PASS/FAIL/verdict field.
- Does not resolve entity identity across documents (e.g., deciding "UPS-01"
  in one doc and "Uninterruptible Power Supply Unit 1" in another are the same
  equipment) beyond a confidence-scored suggestion — final resolution needs a
  human confirm step. This is flagged in the source evaluation as a known hard
  problem and a top production risk; we don't pretend to solve it silently.

## Pipeline internally

1. **Parse**: `pdfplumber`/`Docling` for PDFs (born-digital vendor cut-sheets);
   plain-text passthrough for `.txt` submittals like the dataset's.
2. **Table extraction**: hybrid approach — LLM identifies table regions, a
   deterministic parser extracts cell values, to minimize hallucination on the
   hardest part of this pipeline (per the source evaluation's own guidance,
   citing the arXiv OCR-LLM literature on this exact failure mode).
3. **Few-shot LLM extraction** (Groq) into the typed schema below, with the
   spec's expected attribute vocabulary passed as extraction guidance so the
   model isn't guessing field names from scratch.
4. **Deterministic units normalization** (kA vs kAIC vs A, % vs decimal, etc.)
   — this step is plain Python, not a second model call.

## API contract

### `POST /extraction/submittal`

Request:
```json
{
  "equipment_id_hint": "XFMR-01",
  "raw_text": "...(full submittal document text)...",
  "spec_section_hint": "26 12 00"
}
```

Response:
```json
{
  "equipment_id": "XFMR-01",
  "extracted_attributes": [
    {
      "attribute": "impedance_pct",
      "value": 7.0,
      "unit": "%",
      "source_span": "Impedance (Z%): 7.0% at rated tap, measured per factory routine test",
      "confidence": 0.95
    }
  ],
  "extraction_warnings": []
}
```

`extraction_warnings` carries flags like `"table extraction below confidence threshold"`
or `"equipment tag ambiguous, see entity_resolution_candidates"` — these should
surface in the UI as review prompts, not be silently dropped.

## Test plan

Extraction F1 against `dataset/gold_set/compliance_gold_set.csv`'s
`submitted_value` column, run over all 5 raw submittal files in
`dataset/submittals/*.txt`. Target ≥0.90 precision/recall on this curated set
before considering the extraction step demo-ready (per the source evaluation's
"if table extraction is <80%, hard-code the demo equipment set" threshold —
we're aiming above that floor, not just clearing it).
