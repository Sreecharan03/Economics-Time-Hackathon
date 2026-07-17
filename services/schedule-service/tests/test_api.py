"""
End-to-end tests through the real FastAPI endpoint. API-layer tests focus on
contract/wiring correctness (request validation, response shaping, error
codes) -- the deep algorithmic edge cases are already covered at the engine
level in test_engine.py's Hypothesis properties; duplicating that here would
just be the same coverage twice, not new coverage.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_scenario_a_transformer_critical_matches_gold_set():
    """The headline demo result: XFMR-01 +14 days -> IST slips 745 -> 759."""
    r = client.post("/schedule/propagate", json={"equipment_id": "XFMR-01", "resubmit_delay_days": 14})
    assert r.status_code == 200
    body = r.json()
    assert body["triggering_activity"] == "SUBM-XFMR-01"
    assert body["milestone_impact"]["activity_id"] == "CX-L5-IST"
    assert body["milestone_impact"]["baseline_early_finish"] == 745
    assert body["milestone_impact"]["new_early_finish"] == 759
    assert body["milestone_impact"]["slip_days"] == 14
    assert body["milestone_impact"]["critical"] is True
    assert body["urgency"] == "CRITICAL"


def test_scenario_b_switchgear_flagged_not_critical():
    r = client.post("/schedule/propagate", json={"equipment_id": "SWGR-MV-01", "resubmit_delay_days": 14})
    assert r.status_code == 200
    body = r.json()
    assert body["milestone_impact"]["baseline_early_finish"] == 745
    assert body["milestone_impact"]["new_early_finish"] == 745
    assert body["milestone_impact"]["slip_days"] == 0
    assert body["milestone_impact"]["critical"] is False
    assert body["urgency"] == "FLAGGED"
    # switchgear's own chain must still show up as affected (float consumed),
    # even though the milestone itself doesn't move
    affected_ids = {a["activity_id"] for a in body["affected_activities"]}
    assert "SUBM-SWGR-01" in affected_ids
    assert "FAB-SWGR-01" in affected_ids


def test_affected_activities_excludes_unaffected_ones():
    """GEN-01 and CRAC-01's chains share nothing with the switchgear chain
    -- they must NOT appear in affected_activities for a switchgear delay."""
    r = client.post("/schedule/propagate", json={"equipment_id": "SWGR-MV-01", "resubmit_delay_days": 14})
    affected_ids = {a["activity_id"] for a in r.json()["affected_activities"]}
    assert "FAB-GEN-01" not in affected_ids
    assert "INST-GEN-01" not in affected_ids
    assert "FAB-CRAC-01" not in affected_ids


def test_zero_delay_returns_no_affected_activities():
    r = client.post("/schedule/propagate", json={"equipment_id": "XFMR-01", "resubmit_delay_days": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["affected_activities"] == []
    assert body["milestone_impact"]["slip_days"] == 0
    assert body["urgency"] == "FLAGGED"


def test_custom_milestone_activity_id():
    """Querying a different milestone than the IST default -- e.g. handover
    -- must be honored, not silently ignored in favor of the default."""
    r = client.post("/schedule/propagate", json={
        "equipment_id": "XFMR-01", "resubmit_delay_days": 14, "milestone_activity_id": "CX-L6-HANDOVER",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["milestone_impact"]["activity_id"] == "CX-L6-HANDOVER"
    assert body["milestone_impact"]["slip_days"] == 14


# ---------------------------------------------------------------------------
# Error paths.
# ---------------------------------------------------------------------------

def test_unknown_equipment_id_returns_404():
    r = client.post("/schedule/propagate", json={"equipment_id": "NOT-REAL", "resubmit_delay_days": 14})
    assert r.status_code == 404


def test_equipment_with_no_schedule_activity_returns_404():
    r = client.post("/schedule/propagate", json={"equipment_id": "PDU-01", "resubmit_delay_days": 14})
    assert r.status_code == 404


def test_unknown_milestone_activity_id_returns_404():
    r = client.post("/schedule/propagate", json={
        "equipment_id": "XFMR-01", "resubmit_delay_days": 14, "milestone_activity_id": "NOT-REAL",
    })
    assert r.status_code == 404


def test_negative_delay_rejected_by_schema():
    r = client.post("/schedule/propagate", json={"equipment_id": "XFMR-01", "resubmit_delay_days": -5})
    assert r.status_code == 422  # pydantic Field(ge=0) violation


def test_missing_equipment_id_rejected_by_schema():
    r = client.post("/schedule/propagate", json={"resubmit_delay_days": 14})
    assert r.status_code == 422


def test_missing_resubmit_delay_days_rejected_by_schema():
    r = client.post("/schedule/propagate", json={"equipment_id": "XFMR-01"})
    assert r.status_code == 422


def test_non_integer_delay_rejected_by_schema():
    r = client.post("/schedule/propagate", json={"equipment_id": "XFMR-01", "resubmit_delay_days": "not-a-number"})
    assert r.status_code == 422
