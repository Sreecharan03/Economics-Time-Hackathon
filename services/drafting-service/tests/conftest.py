import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import (
    ComplianceAttributeResult,
    ComplianceResult,
    DraftRfiRequest,
    PrecedentRfi,
    ScheduleMilestoneImpact,
    ScheduleResult,
)


@pytest.fixture()
def xfmr01_request() -> DraftRfiRequest:
    """Mirrors the real shape returned by compliance-service (XFMR-01, FAIL)
    and schedule-service (critical scenario) for the hero demo case."""
    compliance = ComplianceResult(
        equipment_id="XFMR-01",
        overall_verdict="FAIL",
        results=[
            ComplianceAttributeResult(
                attribute="impedance_pct",
                submitted_value=7.0,
                required_value=5.75,
                unit="%",
                verdict="FAIL",
                spec_section="26 12 00.3",
                rationale="Submitted impedance 7.0% exceeds the acceptable tolerance band of 5.32-6.18%.",
            )
        ],
    )
    schedule = ScheduleResult(
        triggering_activity="SUBM-XFMR-01",
        milestone_impact=ScheduleMilestoneImpact(
            activity_id="CX-L5-IST", activity_name="Integrated Systems Test / White Tag (Level 5)",
            slip_days=14, critical=True,
        ),
        urgency="CRITICAL",
    )
    precedent = [
        PrecedentRfi(
            rfi_id="RFI-HIST-003",
            source_project="Ashburn Campus Building 4",
            resolution="EOR confirmed 7% falls outside tolerance; required custom low-impedance wind.",
        )
    ]
    return DraftRfiRequest(
        equipment_id="XFMR-01", compliance_result=compliance, schedule_result=schedule, precedent=precedent
    )
