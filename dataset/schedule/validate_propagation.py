"""
Independent verification of schedule_propagation_gold_set.csv.

validate_cpm.py already proved the BASELINE network (no deviation) is
internally consistent. This script closes a real gap: the gold set's
"new_early_finish"/"new_total_float" columns (what happens after a 14-day
resubmit delay is applied) were computed by hand and were never independently
recomputed -- unlike the baseline, which was. Given a hand-computed CPM
number in this same dataset was already found wrong once (the switchgear
263-vs-273 float bug), the propagation numbers get no benefit of the doubt
until an independent forward/backward pass confirms them too.

Reuses the same parsing/CPM logic as validate_cpm.py (duplicated rather than
imported to keep this a standalone, auditable script).
"""
import csv
import re
import sys
from pathlib import Path

SCHED_DIR = Path(__file__).parent
GOLD = SCHED_DIR.parent / "gold_set" / "schedule_propagation_gold_set.csv"


def load_schedule():
    with open(SCHED_DIR / "schedule.csv") as f:
        return list(csv.DictReader(f))


def parse_preds(raw):
    out = []
    if not raw:
        return out
    for tok in raw.split(","):
        tok = tok.strip()
        m = re.match(r"([A-Za-z0-9\-]+):FS\+?(\d+)?", tok)
        if not m:
            raise ValueError(f"Unparseable predecessor token: {tok!r}")
        out.append((m.group(1), int(m.group(2) or 0)))
    return out


def run_cpm(durations, preds):
    """Full forward + backward pass. durations: {activity_id: int}."""
    succs = {aid: [] for aid in durations}
    for aid, plist in preds.items():
        for pid, lag in plist:
            succs[pid].append((aid, lag))

    ES, EF = {}, {}
    remaining = set(durations)
    changed = True
    while remaining and changed:
        changed = False
        for aid in list(remaining):
            plist = preds[aid]
            if all(pid in EF for pid, _ in plist):
                es = max((EF[pid] + lag for pid, lag in plist), default=0)
                ES[aid] = es
                EF[aid] = es + durations[aid]
                remaining.discard(aid)
                changed = True
    if remaining:
        raise RuntimeError(f"forward pass stuck: {remaining}")

    project_finish = max(EF.values())
    LS, LF = {}, {}
    remaining = set(durations)
    changed = True
    while remaining and changed:
        changed = False
        for aid in list(remaining):
            slist = succs[aid]
            if not slist:
                LF[aid] = project_finish
                LS[aid] = project_finish - durations[aid]
                remaining.discard(aid)
                changed = True
                continue
            if all(sid in LS for sid, _ in slist):
                lf = min(LS[sid] - lag for sid, lag in slist)
                LF[aid] = lf
                LS[aid] = lf - durations[aid]
                remaining.discard(aid)
                changed = True
    if remaining:
        raise RuntimeError(f"backward pass stuck: {remaining}")

    TF = {aid: LF[aid] - EF[aid] for aid in durations}
    return ES, EF, LS, LF, TF


def main():
    rows = load_schedule()
    base_durations = {r["activity_id"]: int(r["duration_days"]) for r in rows}
    preds = {r["activity_id"]: parse_preds(r["predecessors"]) for r in rows}

    with open(GOLD) as f:
        gold_rows = list(csv.DictReader(f))

    scenarios = {}
    for r in gold_rows:
        scenarios.setdefault(r["scenario"], []).append(r)

    mismatches = []
    checked = 0

    for scenario_name, srows in scenarios.items():
        if scenario_name == "baseline":
            _, EF, _, _, TF = run_cpm(base_durations, preds)
            for r in srows:
                checked += 1
                aid = r["activity_id"]
                exp_ef, exp_tf = int(r["baseline_early_finish"]), int(r["baseline_total_float"])
                if (EF[aid], TF[aid]) != (exp_ef, exp_tf):
                    mismatches.append((scenario_name, aid, "baseline", (EF[aid], TF[aid]), (exp_ef, exp_tf)))
            continue

        trig_activity = srows[0]["triggering_activity"]
        delay = int(srows[0]["resubmit_delay_days"])
        durations = dict(base_durations)
        durations[trig_activity] += delay
        _, EF, _, _, TF = run_cpm(durations, preds)

        print(f"\n=== {scenario_name}: +{delay}d on {trig_activity} ===")
        print(f"{'activity_id':16s} {'gold_new_EF':>12s} {'recomputed_EF':>14s} {'gold_new_TF':>12s} {'recomputed_TF':>14s}  match?")
        for r in srows:
            checked += 1
            aid = r["activity_id"]
            exp_ef, exp_tf = int(r["new_early_finish"]), int(r["new_total_float"])
            got_ef, got_tf = EF[aid], TF[aid]
            ok = (got_ef, got_tf) == (exp_ef, exp_tf)
            print(f"{aid:16s} {exp_ef:12d} {got_ef:14d} {exp_tf:12d} {got_tf:14d}  {'OK' if ok else 'MISMATCH'}")
            if not ok:
                mismatches.append((scenario_name, aid, "propagated", (got_ef, got_tf), (exp_ef, exp_tf)))

    print(f"\nChecked {checked} gold-set rows across {len(scenarios)} scenarios.")
    if mismatches:
        print(f"\nFAIL: {len(mismatches)} mismatch(es):")
        for scen, aid, kind, got, exp in mismatches:
            print(f"  [{scen}] {aid} ({kind}): recomputed={got} gold={exp}")
        sys.exit(1)
    else:
        print("PASS: every gold-set row matches an independent forward/backward-pass recomputation.")


if __name__ == "__main__":
    main()
