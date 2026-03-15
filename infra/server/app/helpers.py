"""Shared request-processing helpers used across routers."""

import logging

from fastapi import Request

from . import audit

logger = logging.getLogger("policy-server")


def format_response(result: dict) -> dict:
    """Normalize an OPA result into {allow, violations} with sorted violations."""
    return {
        "allow": result.get("allow", False),
        "violations": sorted(
            result.get("violations", []), key=lambda v: v.get("code", "")
        ),
    }


def record_audit(
    policy: str,
    result: dict,
    input_data: dict,
    request: Request,
    source: str = "api",
) -> dict:
    """Format result, record an audit event, and return the enriched response."""
    resp = format_response(result)
    event = audit.record(
        policy=policy,
        decision=resp["allow"],
        violations=resp["violations"],
        input_data=input_data,
        actor=request.headers.get("X-Actor", ""),
        source=source,
    )
    resp["audit_id"] = event["id"]
    logger.info(
        "policy=%s decision=%s audit_id=%s",
        policy,
        event["decision"],
        event["id"],
    )
    return resp
