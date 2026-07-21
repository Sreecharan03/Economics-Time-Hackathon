"""
Thin async HTTP clients for the five downstream services. No orchestration
logic here -- see orchestrator.py. Every call goes through `post_json` so
network failures (service down/unreachable) and HTTP error responses (4xx/5xx
from a healthy-but-rejecting service) are distinguished consistently and
raised as typed exceptions the orchestrator can handle per-service.
"""
from __future__ import annotations

import os

import httpx

DEFAULT_URLS = {
    "extraction-service": "http://localhost:8001",
    "compliance-service": "http://localhost:8002",
    "schedule-service": "http://localhost:8003",
    "retrieval-service": "http://localhost:8004",
    "drafting-service": "http://localhost:8005",
}

ENV_VARS = {
    "extraction-service": "EXTRACTION_SERVICE_URL",
    "compliance-service": "COMPLIANCE_SERVICE_URL",
    "schedule-service": "SCHEDULE_SERVICE_URL",
    "retrieval-service": "RETRIEVAL_SERVICE_URL",
    "drafting-service": "DRAFTING_SERVICE_URL",
}


def service_url(service_name: str) -> str:
    return os.environ.get(ENV_VARS[service_name], DEFAULT_URLS[service_name])


class ServiceUnavailable(RuntimeError):
    """The service could not be reached at all (connection refused, timeout, DNS)."""

    def __init__(self, service_name: str, detail: str):
        self.service_name = service_name
        self.detail = detail
        super().__init__(f"{service_name} unavailable: {detail}")


class ServiceHTTPError(RuntimeError):
    """The service responded, but with an error status code."""

    def __init__(self, service_name: str, status_code: int, detail: str):
        self.service_name = service_name
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{service_name} returned HTTP {status_code}: {detail}")


async def post_json(client: httpx.AsyncClient, service_name: str, path: str, payload: dict, timeout: float = 30.0) -> dict:
    url = f"{service_url(service_name)}{path}"
    try:
        resp = await client.post(url, json=payload, timeout=timeout)
    except httpx.RequestError as e:
        raise ServiceUnavailable(service_name, str(e)) from e
    if resp.status_code >= 400:
        raise ServiceHTTPError(service_name, resp.status_code, resp.text)
    return resp.json()


async def call_extraction(client: httpx.AsyncClient, equipment_id_hint: str, raw_text: str, spec_section_hint: str | None = None) -> dict:
    return await post_json(
        client,
        "extraction-service",
        "/extraction/submittal",
        {"equipment_id_hint": equipment_id_hint, "raw_text": raw_text, "spec_section_hint": spec_section_hint},
    )


async def call_compliance(client: httpx.AsyncClient, equipment_id: str, extracted_attributes: list[dict]) -> dict:
    return await post_json(
        client,
        "compliance-service",
        "/compliance/check",
        {"equipment_id": equipment_id, "extracted_attributes": extracted_attributes},
    )


async def call_schedule(client: httpx.AsyncClient, equipment_id: str, resubmit_delay_days: int = 14) -> dict:
    return await post_json(
        client,
        "schedule-service",
        "/schedule/propagate",
        {"equipment_id": equipment_id, "resubmit_delay_days": resubmit_delay_days},
    )


async def call_retrieval(client: httpx.AsyncClient, query_text: str, top_k: int = 3) -> dict:
    return await post_json(
        client, "retrieval-service", "/retrieval/similar-rfis", {"query_text": query_text, "top_k": top_k}
    )


async def call_drafting(
    client: httpx.AsyncClient, equipment_id: str, compliance_result: dict, schedule_result: dict | None, precedent: list[dict]
) -> dict:
    return await post_json(
        client,
        "drafting-service",
        "/drafting/rfi",
        {
            "equipment_id": equipment_id,
            "compliance_result": compliance_result,
            "schedule_result": schedule_result,
            "precedent": precedent,
        },
    )
