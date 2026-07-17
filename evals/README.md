# evals

Scripts that score the platform against `dataset/gold_set/*.csv` — this is how
"is it demo-ready" gets answered with a number instead of a feeling.

## What exists today

- `check_dataset_integrity.py` — cross-file referential integrity (equipment
  IDs, activity IDs, schema completeness). Run in CI on every push.
  `dataset/schedule/validate_cpm.py` is the schedule-specific counterpart
  (independent CPM recomputation, also run in CI).

## Planned, not yet built

- `eval_compliance.py` — runs all 14 rows of `dataset/gold_set/compliance_gold_set.csv`
  through `compliance-service` and reports precision/recall/F1 per verdict class.
  Target: 100% on this curated set before considering the service correct (it's
  a deterministic rule engine being checked against known-correct math, not a
  fuzzy classifier — anything short of 100% here is a bug, not an acceptable
  eval score).
- `eval_schedule.py` — runs both seeded scenarios from
  `dataset/gold_set/schedule_propagation_gold_set.csv` through `schedule-service`
  and asserts exact Early Finish / Total Float matches, same reasoning as above.
- `eval_extraction.py` — extraction F1 against the `submitted_value` column of
  the compliance gold set, run over the raw files in `dataset/submittals/*.txt`.
  This one *is* allowed to be <100% (LLM extraction from unstructured text is
  the one genuinely fuzzy step in the pipeline) — target ≥0.90 per the source
  evaluation's demo-readiness threshold.
- `eval_retrieval.py` — hit-rate@3 for RFI retrieval. Needs a gold mapping file
  (deviation → known-relevant RFI ID) written first; see
  `services/retrieval-service/README.md` for the mapping this should use.

## Why deterministic-service evals are pass/fail, not a percentage

`compliance-service` and `schedule-service` do not involve an LLM. A wrong
answer from either is a code bug, not model variance — so their evals are
written as exact-match assertions (fail CI on any mismatch), not thresholds.
Only `eval_extraction.py` and `eval_retrieval.py`, which depend on model
behavior, use a percentage threshold instead of exact match.
