# evals

Scripts that score the platform against `dataset/gold_set/*.csv` — this is how
"is it demo-ready" gets answered with a number instead of a feeling.

## What exists today

- `check_dataset_integrity.py` — cross-file referential integrity (equipment
  IDs, activity IDs, schema completeness, plus a sanity check that every
  `boundary_test` row's own numbers are internally coherent). Run in CI on
  every push.
- `dataset/schedule/validate_cpm.py` — independent CPM recomputation of the
  baseline (no-deviation) schedule network. Also run in CI.
- `dataset/schedule/validate_propagation.py` — independent recomputation of
  both seeded delay scenarios (transformer/critical, switchgear/flagged)
  against `schedule_propagation_gold_set.csv`. This one exists specifically
  because the baseline being independently verified didn't mean the
  *propagated* numbers were — they were hand-patched once after the baseline
  bug and never re-verified until this script was written.

`compliance_gold_set.csv` has two `row_type` values: `equipment` (the 12
real demo-project items, 14 rows since UPS-01/UPS-02 each have two checked
attributes) and `boundary_test` (7 synthetic numeric vectors probing the
exact edges of the tolerance-band and minimum-threshold checks — these
don't correspond to real equipment and are excluded from the
equipment-master cross-reference on purpose). Neither is the eventual
~1000-case parametrized suite `compliance-service` needs before it can push
— that suite is generated programmatically against the comparison function
directly, not hand-typed into a CSV. These 21 rows are the *seed*/regression
set, not a substitute for it.

## Planned, not yet built

- `eval_compliance.py` — runs all rows of `dataset/gold_set/compliance_gold_set.csv`
  (both `row_type`s) through `compliance-service` and reports precision/recall/F1
  per verdict class. Target: 100% on this curated set before considering the
  service correct (it's a deterministic rule engine being checked against
  known-correct math, not a fuzzy classifier — anything short of 100% here is
  a bug, not an acceptable eval score).
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
