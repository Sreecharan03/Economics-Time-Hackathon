"""
Referential-integrity check across dataset/ files. Run from repo root:

    python3 evals/check_dataset_integrity.py

Exits non-zero on any check failure so CI catches drift between
equipment_master.json, the gold sets, schedule.csv, and rfis.json.
"""
import csv
import json
import sys
from pathlib import Path

DATASET = Path(__file__).parent.parent / "dataset"


def fail(msg):
    print(f"FAIL: {msg}")
    return False


def main():
    ok = True

    with open(DATASET / "submittals" / "equipment_master.json") as f:
        equip = json.load(f)["equipment"]
    equip_ids = {e["equipment_id"] for e in equip}

    with open(DATASET / "gold_set" / "compliance_gold_set.csv") as f:
        gold_rows = list(csv.DictReader(f))
    gold_ids = {r["equipment_id"] for r in gold_rows}

    if equip_ids - gold_ids:
        ok = fail(f"equipment in master but missing from compliance gold set: {equip_ids - gold_ids}")
    if gold_ids - equip_ids:
        ok = fail(f"equipment in compliance gold set but not in master: {gold_ids - equip_ids}")

    for r in gold_rows:
        eid = r["equipment_id"]
        e = next(x for x in equip if x["equipment_id"] == eid)
        if "attributes" in e:
            att = next((a for a in e["attributes"] if a["attribute"] == r["attribute"]), None)
            if att is None:
                ok = fail(f"{eid}/{r['attribute']}: attribute in gold set not found in master's attributes[]")
                continue
            expected_pass = r["expected_verdict"] == "PASS"
            if att["pass"] != expected_pass:
                ok = fail(f"{eid}/{r['attribute']}: master pass={att['pass']} vs gold verdict={r['expected_verdict']}")
        else:
            if e.get("attribute") != r["attribute"]:
                continue
            if e["verdict"] != r["expected_verdict"]:
                ok = fail(f"{eid}: master verdict={e['verdict']} vs gold verdict={r['expected_verdict']}")

    with open(DATASET / "schedule" / "schedule.csv") as f:
        sched_rows = list(csv.DictReader(f))
    sched_equip_refs = set()
    for r in sched_rows:
        if r["equipment_id"]:
            sched_equip_refs.update(tok.strip() for tok in r["equipment_id"].split(","))
    if sched_equip_refs - equip_ids:
        ok = fail(f"schedule.csv references unknown equipment: {sched_equip_refs - equip_ids}")

    act_ids = {r["activity_id"] for r in sched_rows}
    for r in sched_rows:
        if not r["predecessors"]:
            continue
        for tok in r["predecessors"].split(","):
            pid = tok.strip().split(":")[0]
            if pid not in act_ids:
                ok = fail(f"{r['activity_id']}: dangling predecessor reference {pid!r}")

    with open(DATASET / "rfis" / "rfis.json") as f:
        rfis = json.load(f)
    required_keys = {"rfi_id", "source_project", "date", "subject", "question",
                      "spec_section", "equipment_type", "resolution", "tags"}
    for r in rfis:
        if not required_keys.issubset(r.keys()):
            ok = fail(f"{r.get('rfi_id', '?')}: missing required RFI fields {required_keys - r.keys()}")

    if ok:
        print(f"PASS: {len(equip_ids)} equipment, {len(gold_rows)} gold rows, "
              f"{len(sched_rows)} schedule activities, {len(rfis)} RFIs -- all cross-references consistent")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
