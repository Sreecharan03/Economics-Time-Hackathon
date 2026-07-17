# compliance-service

## Responsibility

Compare extracted submittal attribute values against spec-defined thresholds and
return a verdict. **This service never calls an LLM.** It is a pure comparison
engine — numeric range checks, enum matches, tolerance-band math — because its
output feeds engineering coordination decisions where "usually right" is not an
acceptable failure mode. If a rule can't be expressed as a deterministic
comparison (e.g., a genuinely ambiguous free-text requirement), the correct
output is `CONFLICT` or `NEEDS_HUMAN_REVIEW`, never a best-guess PASS/FAIL.

## What it does NOT do

- Does not extract values from raw documents (that's `extraction-service`).
- Does not decide schedule impact (that's `schedule-service`).
- Does not draft RFI text (that's `drafting-service`).
- Does not auto-resolve conflicting spec requirements — see `dataset/specs/`
  Section 26 36 00 (the ATS transfer-time example) for why: some deviations are
  the spec contradicting itself, not a vendor error, and the correct behavior
  is to surface that for human resolution, not silently pick a side.

## API contract

### `POST /compliance/check`

Request:
```json
{
  "equipment_id": "XFMR-01",
  "extracted_attributes": [
    {"attribute": "impedance_pct", "value": 7.0, "unit": "%"}
  ]
}
```

Response:
```json
{
  "equipment_id": "XFMR-01",
  "overall_verdict": "FAIL",
  "results": [
    {
      "attribute": "impedance_pct",
      "submitted_value": 7.0,
      "required_value": 5.75,
      "tolerance_pct": 7.5,
      "acceptable_range": [5.32, 6.18],
      "unit": "%",
      "verdict": "FAIL",
      "spec_section": "26 12 00.3",
      "rationale": "Submitted impedance 7.0% exceeds acceptable tolerance band 5.32-6.18% derived from spec nominal 5.75% +/-7.5% (ANSI/IEEE C57.12.90)."
    }
  ]
}
```

`verdict` is one of `PASS`, `FAIL`, `CONFLICT`. `CONFLICT` is returned when the
spec itself contains contradictory requirements for the same attribute (see the
`ATS-01` case in `dataset/gold_set/compliance_gold_set.csv`) — the response
includes a `conflicting_clauses` array instead of a single `required_value` in
that case.

## Data dependency

Reads spec thresholds from Postgres (`spec_requirement` table, populated at
project setup from `dataset/specs/project_meridian_dh1_spec.md` — parsing that
markdown into structured threshold rows is a one-time seed step, not something
this service does at request time).

## Test plan

Unit tests run the full `dataset/gold_set/compliance_gold_set.csv` (14 rows,
6 PASS / 5 FAIL / 1 CONFLICT) through this service and assert every verdict
matches exactly — this is the eval, not just a smoke test. Zero tolerance for
a silent verdict flip; any mismatch fails CI.
