"""
FastAPI wrapper around the deterministic compliance engine. This file
contains zero comparison logic itself -- it only validates the request shape,
looks up spec requirements, calls engine.check_compliance, and shapes the
response per README.md's contract. See engine.py for the actual rules; see
spec_data.py for where requirements come from.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.engine import ComplianceEngineError, check_compliance, rollup_verdict
from app.models import AttributeResult, ComplianceCheckRequest, ComplianceCheckResponse
from app.spec_data import get_requirement

app = FastAPI(title="compliance-service")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/compliance/check", response_model=ComplianceCheckResponse)
def compliance_check(req: ComplianceCheckRequest) -> ComplianceCheckResponse:
    results: list[AttributeResult] = []
    verdicts = []
    for attr in req.extracted_attributes:
        try:
            requirement = get_requirement(req.equipment_id, attr.attribute)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        try:
            result = check_compliance(attr.value, requirement, submitted_unit=attr.unit)
        except ComplianceEngineError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        verdicts.append(result.verdict)

        conflicting = None
        if requirement.conflicting_clauses:
            conflicting = [
                {"clause": c.clause, "required_value": c.required_value, "unit": c.unit}
                for c in requirement.conflicting_clauses
            ]

        acceptable_range = None
        if result.acceptable_range_low is not None or result.acceptable_range_high is not None:
            acceptable_range = (result.acceptable_range_low, result.acceptable_range_high)

        results.append(
            AttributeResult(
                attribute=result.attribute,
                submitted_value=result.submitted_value,
                required_value=result.required_value,
                acceptable_range=acceptable_range,
                unit=requirement.unit,
                verdict=result.verdict.value,
                spec_section=requirement.spec_clause,
                rationale=result.rationale,
                conflicting_clauses=conflicting,
            )
        )

    overall = rollup_verdict(verdicts)

    return ComplianceCheckResponse(
        equipment_id=req.equipment_id,
        overall_verdict=overall.value,
        results=results,
    )
