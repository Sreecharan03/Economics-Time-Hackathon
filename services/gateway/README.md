# gateway

## Responsibility

Owns the end-to-end request lifecycle for a submittal review and is the only
service the frontend talks to. Calls the other five services in order,
assembles the combined result, and is the natural place for cross-cutting
concerns (auth, rate limiting, request logging) once those exist. Contains
no domain logic of its own — every judgment call (compliance, schedule,
retrieval, drafting) is delegated; the gateway only sequences the calls.

## Orchestration order for one request

```
1. extraction-service     (raw submittal text -> typed attributes)
2. compliance-service      (typed attributes -> verdict)
3. IF verdict == FAIL:
      schedule-service     (equipment_id + 14-day resubmit delay -> milestone impact)
      retrieval-service    (deviation description -> precedent RFIs)   } run in parallel
4. IF verdict == FAIL:
      drafting-service     (compliance + schedule + precedent -> draft RFI)
5. Assemble and return the combined result.
```

If `compliance-service` returns `PASS`, steps 3-4 are skipped entirely — no
schedule call, no retrieval call, no drafting call, no wasted LLM spend on a
compliant submittal. If it returns `CONFLICT` (spec-internal contradiction,
e.g. the ATS-01 case), schedule/retrieval/drafting still run, but the drafted
output is framed as "clarification needed" rather than "deviation found."

## API contract

### `POST /review/submittal`

Request:
```json
{
  "equipment_id_hint": "XFMR-01",
  "raw_submittal_text": "...(full submittal document)..."
}
```

Response: the assembled result of the pipeline above — extraction output,
compliance verdict, schedule impact (if applicable), retrieved precedent (if
applicable), and drafted RFI (if applicable), plus a top-level
`requires_human_approval: true` flag that is always present when any AI-derived
content is included in the response.

## Test plan

Integration tests run the full pipeline end-to-end for all 12 equipment items
in `dataset/submittals/equipment_master.json` against a docker-compose stack
of all six services, and assert the final assembled verdict/urgency matches
`dataset/gold_set/compliance_gold_set.csv` and
`dataset/gold_set/schedule_propagation_gold_set.csv`. This is the test that
actually proves the "compliance → schedule → commissioning" chain works
end-to-end, not just that each service passes its own unit tests in isolation.
