"""
Independent CPM forward/backward-pass recomputation, used to verify that the
hand-computed early_start/early_finish/late_start/late_finish/total_float_days
columns already recorded in schedule.csv are internally consistent.

This does NOT trust the CSV's own ES/EF/LS/LF/TF columns as input -- it recomputes
them from scratch using only: activity_id, duration_days, predecessors (with FS
or FS+lag relationships). It then diffs the recomputed values against what's on
disk and reports any mismatch.
"""
import csv
import re
import sys

def load(path):
    with open(path) as f:
        return list(csv.DictReader(f))

def parse_preds(raw):
    # format: "ACT1:FS,ACT2:FS" or "ACT1:FS+34" or ""
    out = []
    if not raw:
        return out
    for tok in raw.split(","):
        tok = tok.strip()
        m = re.match(r"([A-Za-z0-9\-]+):FS\+?(\d+)?", tok)
        if not m:
            raise ValueError(f"Unparseable predecessor token: {tok!r}")
        pred_id, lag = m.group(1), int(m.group(2) or 0)
        out.append((pred_id, lag))
    return out

def main():
    rows = load("schedule.csv")
    acts = {r["activity_id"]: r for r in rows}
    dur = {aid: int(r["duration_days"]) for aid, r in acts.items()}
    preds = {aid: parse_preds(r["predecessors"]) for aid, r in acts.items()}

    # build successors map for backward pass
    succs = {aid: [] for aid in acts}
    for aid, plist in preds.items():
        for pid, lag in plist:
            succs[pid].append((aid, lag))

    # topological order via repeated relaxation (small graph, fine to just
    # iterate until stable rather than writing a proper topo sort)
    ES, EF = {}, {}
    remaining = set(acts)
    changed = True
    while remaining and changed:
        changed = False
        for aid in list(remaining):
            plist = preds[aid]
            if all(pid in EF for pid, lag in plist):
                es = 0
                for pid, lag in plist:
                    es = max(es, EF[pid] + lag)
                ES[aid] = es
                EF[aid] = es + dur[aid]
                remaining.discard(aid)
                changed = True
    if remaining:
        print(f"ERROR: could not resolve activities (cycle or missing preds?): {remaining}")
        sys.exit(1)

    project_finish = max(EF.values())

    LS, LF = {}, {}
    remaining = set(acts)
    changed = True
    while remaining and changed:
        changed = False
        for aid in list(remaining):
            succ_list = succs[aid]
            if not succ_list:
                lf = project_finish
                LF[aid] = lf
                LS[aid] = lf - dur[aid]
                remaining.discard(aid)
                changed = True
                continue
            if all(sid in LS for sid, lag in succ_list):
                lf = min(LS[sid] - lag for sid, lag in succ_list)
                LF[aid] = lf
                LS[aid] = lf - dur[aid]
                remaining.discard(aid)
                changed = True
    if remaining:
        print(f"ERROR: backward pass could not resolve: {remaining}")
        sys.exit(1)

    TF = {aid: LF[aid] - EF[aid] for aid in acts}

    print(f"{'activity_id':16s} {'ES':>5s} {'EF':>5s} {'LS':>5s} {'LF':>5s} {'TF':>5s}  match?")
    mismatches = []
    for aid in acts:
        r = acts[aid]
        recomputed = (ES[aid], EF[aid], LS[aid], LF[aid], TF[aid])
        recorded = (int(r["early_start"]), int(r["early_finish"]),
                    int(r["late_start"]), int(r["late_finish"]),
                    int(r["total_float_days"]))
        ok = recomputed == recorded
        if not ok:
            mismatches.append((aid, recomputed, recorded))
        print(f"{aid:16s} {ES[aid]:5d} {EF[aid]:5d} {LS[aid]:5d} {LF[aid]:5d} {TF[aid]:5d}  {'OK' if ok else 'MISMATCH -- recorded='+str(recorded)}")

    print()
    print(f"Project finish (recomputed): Day {project_finish}")
    critical = [aid for aid in acts if TF[aid] == 0]
    print(f"Critical path activities (TF=0): {critical}")
    print()
    if mismatches:
        print(f"FAIL: {len(mismatches)} mismatch(es) between recomputed CPM and schedule.csv")
        for aid, rec, stored in mismatches:
            print(f"  {aid}: recomputed={rec} stored={stored}")
        sys.exit(1)
    else:
        print("PASS: all recomputed ES/EF/LS/LF/TF values match schedule.csv exactly.")

if __name__ == "__main__":
    main()
