from fastapi import APIRouter, Request

from ..helpers import record_audit
from ..opa import query_opa

router = APIRouter(prefix="/evaluate", tags=["evaluate"])


@router.post("/deploy")
async def evaluate_deploy(request: Request, input_data: dict) -> dict:
    result = await query_opa("github/deploy", input_data)
    response = record_audit("deploy", result, input_data, request, source="api")
    response["input"] = input_data
    return response


@router.post("/pullrequest")
async def evaluate_pullrequest(request: Request, input_data: dict) -> dict:
    result = await query_opa("github/pullrequest", input_data)
    response = record_audit("pullrequest", result, input_data, request, source="api")
    response["input"] = input_data
    return response
