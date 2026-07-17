"""
Three layers of coverage, mirroring compliance-service's test_engine.py:

1. Baseline gold-set regression: reproduces dataset/schedule/validate_cpm.py
   as a pytest test -- run_cpm() over the real schedule.csv network must
   match every recorded ES/EF/LS/LF/TF column exactly.
2. Propagation gold-set regression: reproduces
   dataset/schedule/validate_propagation.py -- both seeded scenarios
   (transformer/critical, switchgear/flagged) checked against
   dataset/gold_set/schedule_propagation_gold_set.csv.
3. Hypothesis property tests on synthetic networks -- the edge-case-volume
   layer. Each property is checked against an independently-derived formula
   (e.g. "float on a shorter parallel chain equals the difference in chain
   lengths"), not against the implementation restating itself, so a bug in
   the forward/backward pass would show up as a property violation.
"""
import csv
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.engine import (
    Activity,
    ScheduleEngineError,
    parse_predecessors,
    propagate_delay,
    run_cpm,
)
from app.schedule_data import load_activities

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEDULE_CSV = REPO_ROOT / "dataset" / "schedule" / "schedule.csv"
PROPAGATION_GOLD = REPO_ROOT / "dataset" / "gold_set" / "schedule_propagation_gold_set.csv"


# ---------------------------------------------------------------------------
# 1. Baseline regression -- same check as validate_cpm.py, as a pytest test.
# ---------------------------------------------------------------------------

def _load_schedule_rows():
    with open(SCHEDULE_CSV) as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("row", _load_schedule_rows(), ids=[r["activity_id"] for r in _load_schedule_rows()])
def test_baseline_matches_recorded_schedule_csv(row):
    activities = load_activities()
    result = run_cpm(activities)
    aid = row["activity_id"]
    assert result.early_start[aid] == int(row["early_start"])
    assert result.early_finish[aid] == int(row["early_finish"])
    assert result.late_start[aid] == int(row["late_start"])
    assert result.late_finish[aid] == int(row["late_finish"])
    assert result.total_float[aid] == int(row["total_float_days"])


def test_baseline_project_finish_is_755():
    activities = load_activities()
    result = run_cpm(activities)
    assert result.project_finish == 755


def test_baseline_critical_path_is_transformer_chain():
    activities = load_activities()
    result = run_cpm(activities)
    critical = {aid for aid, tf in result.total_float.items() if tf == 0}
    expected = {
        "M-NTP", "ENG-010", "SUBM-XFMR-01", "FAB-XFMR-01", "INST-XFMR-01",
        "CX-L2-SAT", "CX-L3-PREFUNC", "CX-L4-FPT", "CX-L5-IST", "CX-L6-HANDOVER",
    }
    assert critical == expected


# ---------------------------------------------------------------------------
# 2. Propagation gold-set regression -- same check as validate_propagation.py.
# ---------------------------------------------------------------------------

def _load_propagation_gold_rows():
    with open(PROPAGATION_GOLD) as f:
        return list(csv.DictReader(f))


_SCENARIOS = {}
for _row in _load_propagation_gold_rows():
    _SCENARIOS.setdefault(_row["scenario"], []).append(_row)


@pytest.mark.parametrize("scenario_name", [s for s in _SCENARIOS if s != "baseline"])
def test_propagation_scenario_matches_gold_set(scenario_name):
    rows = _SCENARIOS[scenario_name]
    equipment_id = rows[0]["triggering_equipment"]
    delay = int(rows[0]["resubmit_delay_days"])

    activities = load_activities()
    result = propagate_delay(activities, equipment_id, delay)

    for row in rows:
        aid = row["activity_id"]
        expected_ef = int(row["new_early_finish"])
        expected_tf = int(row["new_total_float"])
        assert result.propagated.early_finish[aid] == expected_ef, (
            f"[{scenario_name}] {aid}: EF got {result.propagated.early_finish[aid]} expected {expected_ef}"
        )
        assert result.propagated.total_float[aid] == expected_tf, (
            f"[{scenario_name}] {aid}: TF got {result.propagated.total_float[aid]} expected {expected_tf}"
        )


def test_scenario_a_transformer_is_critical():
    activities = load_activities()
    result = propagate_delay(activities, "XFMR-01", 14)
    baseline_ist = result.baseline.early_finish["CX-L5-IST"]
    propagated_ist = result.propagated.early_finish["CX-L5-IST"]
    assert propagated_ist - baseline_ist == 14


def test_scenario_b_switchgear_does_not_slip_ist():
    activities = load_activities()
    result = propagate_delay(activities, "SWGR-MV-01", 14)
    baseline_ist = result.baseline.early_finish["CX-L5-IST"]
    propagated_ist = result.propagated.early_finish["CX-L5-IST"]
    assert propagated_ist == baseline_ist


# ---------------------------------------------------------------------------
# Explicit named edge cases.
# ---------------------------------------------------------------------------

def _chain(*durations: int, ids: list[str] | None = None) -> dict[str, Activity]:
    ids = ids or [f"A{i}" for i in range(len(durations))]
    activities = {}
    for i, (aid, dur) in enumerate(zip(ids, durations)):
        preds = () if i == 0 else ((ids[i - 1], 0),)
        activities[aid] = Activity(aid, aid, "test", dur, preds)
    return activities


def test_empty_network_raises():
    with pytest.raises(ScheduleEngineError):
        run_cpm({})


def test_two_activity_cycle_raises():
    a = Activity("A", "A", "test", 1, (("B", 0),))
    b = Activity("B", "B", "test", 1, (("A", 0),))
    with pytest.raises(ScheduleEngineError):
        run_cpm({"A": a, "B": b})


def test_dangling_predecessor_raises():
    a = Activity("A", "A", "test", 1, (("DOES-NOT-EXIST", 0),))
    with pytest.raises(ScheduleEngineError):
        run_cpm({"A": a})


def test_negative_duration_override_raises():
    activities = _chain(1, 1, 1)
    with pytest.raises(ScheduleEngineError):
        run_cpm(activities, duration_overrides={"A0": -5})


def test_duration_override_for_unknown_activity_raises():
    activities = _chain(1, 1, 1)
    with pytest.raises(ScheduleEngineError):
        run_cpm(activities, duration_overrides={"NOT-REAL": 5})


def test_negative_resubmit_delay_raises():
    activities = load_activities()
    with pytest.raises(ScheduleEngineError):
        propagate_delay(activities, "XFMR-01", -1)


def test_zero_resubmit_delay_is_a_noop():
    activities = load_activities()
    result = propagate_delay(activities, "XFMR-01", 0)
    assert result.propagated.early_finish == result.baseline.early_finish
    assert result.propagated.total_float == result.baseline.total_float


def test_unknown_equipment_id_raises():
    activities = load_activities()
    with pytest.raises(ScheduleEngineError):
        propagate_delay(activities, "NOT-A-REAL-EQUIPMENT", 14)


def test_equipment_with_no_submittal_activity_raises():
    """PDU-01 exists in equipment_master.json but was deliberately never
    added to schedule.csv (it's not a long-lead procurement item in this
    network) -- propagate_delay must fail loudly, not silently no-op."""
    activities = load_activities()
    with pytest.raises(ScheduleEngineError):
        propagate_delay(activities, "PDU-01", 14)


def test_unknown_milestone_activity_id_raises():
    activities = load_activities()
    with pytest.raises(ScheduleEngineError):
        propagate_delay(activities, "XFMR-01", 14, milestone_activity_id="NOT-A-MILESTONE")


def test_predecessor_lag_shifts_early_start():
    a = Activity("A", "A", "test", 10, ())
    b = Activity("B", "B", "test", 5, (("A", 7),))  # 7-day lag after A finishes
    result = run_cpm({"A": a, "B": b})
    assert result.early_finish["A"] == 10
    assert result.early_start["B"] == 10 + 7
    assert result.early_finish["B"] == 10 + 7 + 5


# ---------------------------------------------------------------------------
# Hypothesis property-based tests on synthetic networks.
# ---------------------------------------------------------------------------

_DURATIONS = st.integers(min_value=1, max_value=100)


@settings(max_examples=200)
@given(durations=st.lists(_DURATIONS, min_size=1, max_size=15))
def test_property_linear_chain_is_all_critical(durations):
    """A strict linear chain has no branching, so every activity must be on
    the critical path (TF=0), and EF must be the cumulative sum of durations
    up to that point -- checked against an independently-computed cumsum,
    not the implementation's own running total."""
    ids = [f"A{i}" for i in range(len(durations))]
    activities = _chain(*durations, ids=ids)
    result = run_cpm(activities)

    cumulative = 0
    for aid, dur in zip(ids, durations):
        cumulative += dur
        assert result.early_finish[aid] == cumulative
        assert result.total_float[aid] == 0
    assert result.project_finish == cumulative


@settings(max_examples=250, deadline=None)
@given(
    chain_a=st.lists(_DURATIONS, min_size=1, max_size=8),
    chain_b=st.lists(_DURATIONS, min_size=1, max_size=8),
)
def test_property_diamond_float_equals_chain_length_difference(chain_a, chain_b):
    """Two parallel chains sharing a root and merging into a shared final
    activity: the shorter chain's float must equal exactly the difference
    in total chain length -- the same formula that explains why
    SWGR-MV-01's float is 263 (not a guess, an exact difference) in the
    real dataset. Computed here independently via sum(), not by re-deriving
    it from the CPM result itself."""
    sum_a, sum_b = sum(chain_a), sum(chain_b)

    activities: dict[str, Activity] = {"ROOT": Activity("ROOT", "ROOT", "test", 1, ())}
    a_ids = [f"A{i}" for i in range(len(chain_a))]
    for i, (aid, dur) in enumerate(zip(a_ids, chain_a)):
        preds = (("ROOT", 0),) if i == 0 else ((a_ids[i - 1], 0),)
        activities[aid] = Activity(aid, aid, "test", dur, preds)
    b_ids = [f"B{i}" for i in range(len(chain_b))]
    for i, (bid, dur) in enumerate(zip(b_ids, chain_b)):
        preds = (("ROOT", 0),) if i == 0 else ((b_ids[i - 1], 0),)
        activities[bid] = Activity(bid, bid, "test", dur, preds)
    activities["FINAL"] = Activity("FINAL", "FINAL", "test", 1, ((a_ids[-1], 0), (b_ids[-1], 0)))

    result = run_cpm(activities)

    longer, shorter_ids, diff = (
        (a_ids, b_ids, sum_a - sum_b) if sum_a >= sum_b else (b_ids, a_ids, sum_b - sum_a)
    )
    for aid in longer:
        assert result.total_float[aid] == 0, f"{aid} on the longer/equal chain should be critical"
    for aid in shorter_ids:
        assert result.total_float[aid] == diff, (
            f"{aid} float should equal chain-length difference {diff}, got {result.total_float[aid]}"
        )


@settings(max_examples=150, deadline=None)
@given(
    chain=st.lists(_DURATIONS, min_size=2, max_size=10),
    delay=st.integers(min_value=0, max_value=200),
)
def test_property_delay_on_critical_chain_shifts_milestone_1to1(chain, delay):
    """On a pure linear (fully critical) chain, delaying ANY activity by N
    days shifts the final activity's finish by exactly N days -- this is
    the mechanism behind the transformer/Scenario-A result, generalized."""
    ids = [f"A{i}" for i in range(len(chain))]
    activities = _chain(*chain, ids=ids)
    target = ids[0]  # delay the first activity in the chain

    baseline = run_cpm(activities)
    propagated = run_cpm(activities, duration_overrides={target: chain[0] + delay})

    final_id = ids[-1]
    assert propagated.early_finish[final_id] - baseline.early_finish[final_id] == delay


@settings(max_examples=150, deadline=None)
@given(
    chain_a=st.lists(_DURATIONS, min_size=1, max_size=8),
    chain_b=st.lists(_DURATIONS, min_size=1, max_size=8),
    delay=st.integers(min_value=0, max_value=500),
)
def test_property_delay_on_shorter_chain_absorbed_up_to_float(chain_a, chain_b, delay):
    """Delaying an activity on the shorter of two parallel chains only
    shifts the shared final activity once the delay exceeds that chain's
    float -- and by exactly (delay - float) when it does. This is the exact
    mechanism behind Scenario B (switchgear) not slipping the IST milestone
    for a 14-day delay against 263 days of float."""
    sum_a, sum_b = sum(chain_a), sum(chain_b)
    assume(sum_a != sum_b)  # need one chain to be strictly shorter for "float" to mean anything

    activities: dict[str, Activity] = {"ROOT": Activity("ROOT", "ROOT", "test", 1, ())}
    a_ids = [f"A{i}" for i in range(len(chain_a))]
    for i, (aid, dur) in enumerate(zip(a_ids, chain_a)):
        preds = (("ROOT", 0),) if i == 0 else ((a_ids[i - 1], 0),)
        activities[aid] = Activity(aid, aid, "test", dur, preds)
    b_ids = [f"B{i}" for i in range(len(chain_b))]
    for i, (bid, dur) in enumerate(zip(b_ids, chain_b)):
        preds = (("ROOT", 0),) if i == 0 else ((b_ids[i - 1], 0),)
        activities[bid] = Activity(bid, bid, "test", dur, preds)
    activities["FINAL"] = Activity("FINAL", "FINAL", "test", 1, ((a_ids[-1], 0), (b_ids[-1], 0)))

    shorter_ids, shorter_first_dur, float_amount = (
        (a_ids, chain_a[0], sum_b - sum_a) if sum_a < sum_b else (b_ids, chain_b[0], sum_a - sum_b)
    )
    target = shorter_ids[0]

    baseline = run_cpm(activities)
    propagated = run_cpm(activities, duration_overrides={target: shorter_first_dur + delay})

    expected_slip = max(0, delay - float_amount)
    actual_slip = propagated.early_finish["FINAL"] - baseline.early_finish["FINAL"]
    assert actual_slip == expected_slip


class TestParsePredecessors:
    def test_empty_string(self):
        assert parse_predecessors("") == ()

    def test_single_no_lag(self):
        assert parse_predecessors("ACT1:FS") == (("ACT1", 0),)

    def test_single_with_lag(self):
        assert parse_predecessors("ACT1:FS+34") == (("ACT1", 34),)

    def test_multiple(self):
        assert parse_predecessors("ACT1:FS,ACT2:FS+5") == (("ACT1", 0), ("ACT2", 5))

    def test_malformed_raises(self):
        with pytest.raises(ScheduleEngineError):
            parse_predecessors("not-a-valid-token")

    def test_wrong_relationship_type_raises(self):
        """Only finish-to-start is supported, by design -- a token claiming
        a different relationship type must be rejected, not silently
        treated as FS."""
        with pytest.raises(ScheduleEngineError):
            parse_predecessors("ACT1:SS")
