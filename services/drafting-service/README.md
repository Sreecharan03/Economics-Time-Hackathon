# drafting-service

## Responsibility

Produce a cited RFI/CAR (Corrective Action Request) draft grounded in the
outputs of `compliance-service`, `schedule-service`, and `retrieval-service`.
This is an LLM call (Groq), but a constrained one: the prompt assembly
explicitly injects the verdict, the spec citation, the schedule impact, and
the retrieved precedent as structured context, and the model's job is to
compose readable prose from those facts — not to independently judge
compliance or invent numbers. Every factual claim in the draft (spec clause,
submitted value, schedule impact) must trace back to a field in the request
payload, not be generated freestanding.

## What it does NOT do

- Does not decide the verdict, does not compute schedule impact, does not
  search for precedent — it only composes text from what the other three
  services already determined deterministically or via grounded retrieval.
- Does not auto-send or auto-submit the RFI. Output is always a draft behind
  a human-approval gate — this mirrors the source evaluation's explicit
  guidance that AIA A201 §3.12.5 keeps contractor/engineer responsibility
  intact and no AI tool can absorb that liability.

## API contract

### `POST /drafting/rfi`

Request:
```json
{
  "equipment_id": "XFMR-01",
  "compliance_result": { "...": "compliance-service response for this equipment" },
  "schedule_result": { "...": "schedule-service response for this equipment" },
  "precedent": [ { "rfi_id": "RFI-HIST-003", "resolution": "..." } ]
}
```

Response:
```json
{
  "draft_rfi": {
    "subject": "Transformer XFMR-01 submitted impedance (7.0%) exceeds spec tolerance -- schedule impact review requested",
    "body": "...(full drafted RFI text, citing Section 26 12 00.3, the submitted 7.0% value, the 14-day/IST-critical schedule impact, and precedent RFI-HIST-003)...",
    "citations": [
      {"type": "spec_clause", "ref": "26 12 00.3"},
      {"type": "submittal", "ref": "XFMR-01_submittal.txt"},
      {"type": "schedule_activity", "ref": "CX-L5-IST"},
      {"type": "precedent_rfi", "ref": "RFI-HIST-003"}
    ]
  },
  "requires_human_approval": true
}
```

## Test plan

Every citation in `draft_rfi.citations` must resolve to a real field present
in the request payload — a unit test asserts this structurally (no citation
pointing to something not in the input) rather than trying to grade prose
quality, which is a judgment call, not a pass/fail test.
