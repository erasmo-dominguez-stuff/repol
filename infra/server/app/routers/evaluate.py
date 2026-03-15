"""Direct policy evaluation endpoints.

Callers provide the full OPA input JSON — no transformation layer.
Used for local testing and CI pipelines.
"""

from fastapi import APIRouter, Request

from ..helpers import record_audit
from ..opa import query_opa

router = APIRouter(prefix="/evaluate", tags=["evaluate"])


@router.post("/deploy")
async def evaluate_deploy(request: Request):
    """Evaluate deploy policy. Body = full OPA input JSON."""
    body = await request.json()
    result = await query_opa("github/deploy", body)
    return record_audit("deploy", result, body, request, source="evaluate")


@router.post("/pullrequest")
async def evaluate_pullrequest(request: Request):
    """Evaluate pull request policy. Body = full OPA input JSON."""
    body = await request.json()
    result = await query_opa("github/pullrequest", body)
    return record_audit("pullrequest", result, body, request, source="evaluate")
