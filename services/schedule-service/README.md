# schedule-service

## Responsibility

Given an equipment deviation and a resubmit delay, recompute the CPM network
and report whether a downstream commissioning milestone slips, and by how much.
**This service never calls an LLM.** It is a forward-pass/backward-pass critical
path calculation over finish-to-start activity relationships — the same
algorithm `dataset/schedule/validate_cpm.py` already implements and has been
verified against the hand-built baseline network (see that file's history: it
caught a real 10-day error in the baseline schedule before this service existed
— the exact reason this logic must stay deterministic and independently
testable rather than delegated to a model).

## What it does NOT do

- Does not predict schedule risk via machine learning. nPlan-style ML schedule
  forecasting needs hundreds of thousands of historical projects to calibrate;
  we don't have that data, and pretending otherwise would make every output
  unverifiable. This service reports exact, explainable CPM math only.
- Does not decide whether a deviation *should* trigger a resubmit delay — that
  determination (verdict = FAIL) comes from `compliance-service`; this service
  only answers "if this activity slips N days, what happens downstream."
- Does not touch the database directly for writes — schedule state is read-only
  from this service's perspective; the baseline network lives in
  `dataset/schedule/schedule.csv` / the seeded `schedule_activity` table.

## API contract

### `POST /schedule/propagate`

Request:
```json
{
  "equipment_id": "XFMR-01",
  "resubmit_delay_days": 14
}
```

Response:
```json
{
  "triggering_activity": "SUBM-XFMR-01",
  "milestone_impact": {
    "activity_id": "CX-L5-IST",
    "activity_name": "Integrated Systems Test / White Tag (Level 5)",
    "baseline_early_finish": 745,
    "new_early_finish": 759,
    "slip_days": 14,
    "critical": true
  },
  "affected_activities": [
    {"activity_id": "FAB-XFMR-01", "baseline_early_finish": 686, "new_early_finish": 700, "baseline_total_float": 0, "new_total_float": 0},
    {"activity_id": "INST-XFMR-01", "baseline_early_finish": 700, "new_early_finish": 714, "baseline_total_float": 0, "new_total_float": 0}
  ],
  "urgency": "CRITICAL"
}
```

For a deviation on an activity with float greater than the resubmit delay
(e.g., `SWGR-MV-01`, 263 days float), `milestone_impact.critical` is `false`,
`slip_days` is `0`, and `urgency` is `"FLAGGED"` — the response still reports
the float consumed (`new_total_float`) so the UI can show "263 days remaining"
rather than implying the deviation was ignored.

## Algorithm

1. Load the activity network (`activity_id`, `duration_days`, `predecessors`
   with `FS` or `FS+lag` relationships) from the DB.
2. Locate the triggering equipment's `SUBM-*` activity via `equipment_id`.
3. Add `resubmit_delay_days` to that activity's duration.
4. Full forward pass (recompute Early Start/Early Finish for every activity,
   not just the triggering chain — a single-chain shortcut is exactly the bug
   `validate_cpm.py` caught in the baseline data: an activity can have more
   than one successor, and the *tighter* successor constraint governs float).
5. Full backward pass from the recomputed project finish to get new Late
   Start/Late Finish/Total Float for every activity.
6. Diff against baseline; report the milestone activities.

## Test plan

- Golden-path regression: `dataset/gold_set/schedule_propagation_gold_set.csv`
  encodes both seeded scenarios (transformer = critical, switchgear = flagged
  only) with exact expected Early Finish / Total Float numbers per activity.
  CI runs both scenarios through this service and asserts exact match.
- Property test: forward pass + backward pass on the *unmodified* baseline
  network must reproduce `dataset/schedule/schedule.csv` exactly (this is
  literally what `validate_cpm.py` already does standalone — this service
  wraps that same logic behind an API, it does not reimplement it differently).
