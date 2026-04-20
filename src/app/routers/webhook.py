"""GitHub webhook endpoints (extensible).

This module is the entry point for all GitHub App webhook events.
Responsibilities:
    1. Verify the HMAC-SHA256 signature that GitHub attaches to every request.
    2. Extract relevant fields from the raw webhook payload.
    3. Dispatch to explicit handler registry for normalization/evaluation.
    4. Call OPA to evaluate the policy.
    5. Post the result back to GitHub (Check Run for PRs, callback for deployments).

Extensibility:
    - Handlers for each event type are registered in src/app/handlers/.
    - To add a new policy, create a handler module and register it.

Routes:
    POST /webhook                           — main entry point (routes by X-GitHub-Event)
    POST /webhook/deployment_protection_rule — direct, for deployment events
    POST /webhook/pull_request              — direct, for PR opened/synchronize/etc.
    POST /webhook/pull_request_review       — direct, for review submitted/dismissed
"""
from ..handlers import get_handler
from ..handlers import deploy as _deploy_handler  # noqa: F401
from ..handlers import pull_request as _pull_request_handler  # noqa: F401

import hashlib
import hmac
import json
import logging
import secrets

from fastapi import APIRouter, HTTPException, Request

from ..config import WEBHOOK_SECRET

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

def _verify_signature(request_body: bytes, signature_header: str) -> None:
    if not WEBHOOK_SECRET:
        logger.warning("WEBHOOK_SECRET not configured; signature verification skipped.")
        return
    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), request_body, hashlib.sha256
    ).hexdigest()
    if not secrets.compare_digest(expected, signature_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


async def _parse_event(request: Request) -> tuple[str, dict]:
    raw = await request.body()
    _verify_signature(raw, request.headers.get("X-Hub-Signature-256", ""))
    event_name = request.headers.get("X-GitHub-Event", "")
    if not event_name:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc
    return event_name, payload


@router.post("")
async def webhook_dispatch(request: Request):
    event_name, payload = await _parse_event(request)
    handler = get_handler(event_name)
    if not handler:
        return {"ok": True, "ignored": True, "event": event_name}
    return await handler(request, payload)


@router.post("/deployment_protection_rule")
async def deployment_protection_rule(request: Request):
    _, payload = await _parse_event(request)
    handler = get_handler("deployment_protection_rule")
    if not handler:
        raise HTTPException(status_code=500, detail="Handler not registered")
    return await handler(request, payload)


@router.post("/pull_request")
async def pull_request(request: Request):
    _, payload = await _parse_event(request)
    handler = get_handler("pull_request")
    if not handler:
        raise HTTPException(status_code=500, detail="Handler not registered")
    return await handler(request, payload)


@router.post("/pull_request_review")
async def pull_request_review(request: Request):
    _, payload = await _parse_event(request)
    handler = get_handler("pull_request_review")
    if not handler:
        raise HTTPException(status_code=500, detail="Handler not registered")
    return await handler(request, payload)
