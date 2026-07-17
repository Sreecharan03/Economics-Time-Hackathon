# Schedule dataset notes

`schedule.csv` is a hand-computed, internally consistent CPM network (finish-to-start
relationships only, plus one lag on the two construction activities) representing
Meridian Data Hall 1 from Notice to Proceed (Day 0) through handover (Day 755).

**Critical path (Total Float = 0):**
`M-NTP → ENG-010 → SUBM-XFMR-01 → FAB-XFMR-01 → INST-XFMR-01 → CX-L2-SAT →
CX-L3-PREFUNC → CX-L4-FPT → CX-L5-IST → CX-L6-HANDOVER`

This matches real-world industry data cited in the source evaluation: the transformer
(60–120+ week lead time) is the dominant schedule risk on data centre EPC projects,
not switchgear/UPS/generators, which have materially shorter lead times and therefore
carry large float in this network (see `total_float_days` column).

## How to use this for the delay-propagation demo

The rules-based propagation engine should take an equipment deviation (from
`../submittals/equipment_master.json`, where `verdict: FAIL` triggers a resubmit
cycle) and:

1. Look up the equipment's `SUBM-*` activity in `schedule.csv` via `equipment_id`.
2. Add a resubmit delay (**14 calendar days**, per the source evaluation's cited
   "each resubmit cycle costs roughly 2 weeks") to that activity's duration.
3. Re-run forward pass along all successors (finish-to-start) to get new Early Finish
   dates for every downstream activity.
4. Compare each downstream activity's new Early Finish to its original Total Float.
   If the added delay exceeds the activity's `total_float_days`, the activity becomes
   critical and the amount by which it now exceeds its old Late Finish is the slip
   passed to the next activity in the chain (standard CPM logic).
5. Report whether `CX-L5-IST` (Integrated Systems Test) slips, and by how many days.

## Two seeded scenarios to demo (see `../gold_set/schedule_propagation_gold_set.csv`)

**Scenario A — Transformer impedance deviation (XFMR-01, critical path, TF=0):**
A 14-day resubmit cycle on `SUBM-XFMR-01` propagates 1:1 down the critical path.
Expected result: `CX-L5-IST` slips from Day 745 to Day 759 (**+14 days**, all downstream
milestones including handover also slip 14 days). This is the "hero" demo case —
zero float means the deviation directly threatens the commissioning date.

**Scenario B — Switchgear withstand-rating deviation (SWGR-MV-01, TF=263 days):**
A 14-day resubmit cycle on `SUBM-SWGR-01` is fully absorbed by the chain's 263 days
of float. Expected result: `CX-L5-IST` does **not** slip; float on the switchgear
chain is reduced from 263 to 249 days. This demonstrates the tool correctly
distinguishing "urgent, will blow the schedule" from "real deviation, but not
yet schedule-critical" — the nuance a naive rule ("any deviation = red alert")
would miss, and worth calling out explicitly in the demo narration.

Both scenarios should be surfaced in the UI, but with different urgency framing:
Scenario A as "CRITICAL — commissioning date at risk," Scenario B as "FLAGGED —
compliance issue, monitor float (249 days remaining)."

## Why switchgear float is 263 days, not "time until SAT" (a CPM subtlety worth
## demoing on purpose)

A naive calculation might assume switchgear float = (SAT start day 700) − (switchgear
install finish day 427) = 273 days. That is **wrong**, and this dataset deliberately
keeps the network shaped so a rules-based propagation engine gets it right where a
back-of-envelope guess would not: `INST-SWGR-01` has *two* successors, not one — it
feeds both `CX-L2-SAT` (late start 700) and `INST-UPS-01` (late start 690, because
the UPS cannot be installed until the switchgear bus it connects to is energized).
The binding constraint is the *tighter* of the two, so switchgear's true total float
is 263 days, not 273. `validate_cpm.py` performs a full independent forward/backward
pass (not just a single-chain subtraction) and will catch this class of error —
which is exactly the argument in the source evaluation for keeping this deterministic
Python/CPM rather than an LLM or hand-computed shortcut: a plausible-looking manual
calculation was off by 10 days here until the independent recompute caught it.
