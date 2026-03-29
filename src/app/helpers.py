"""Shared utilities used across router modules.

Keeps common response-formatting and audit-recording logic in one place
so each router only calls ``record_audit`` and gets a fully populated
response dict back.
"""


#TODO: Move this code to audit.py and make it a method on the AuditTrail class, e.g. ``audit_trail.record_and_format(...)``.

import logging

from fastapi import Request

from . import audit

logger = logging.getLogger(__name__)

# Use the injected audit_trail instance

def format_response(result: dict) -> dict:
    """Normalise an OPA result dict into ``{allow, violations}``.

    Violations are sorted by code so responses are deterministic and easy
    to compare in tests.
    """
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
    """Format the OPA result, write an audit event, and return the combined response.

    Returns a dict with ``allow``, ``violations``, and ``audit_id`` keys.
    """
    resp = format_response(result)
    # Use the selected audit_trail implementation
    meta = {
        "client": str(request.client.host) if hasattr(request, "client") else None,
        "headers": dict(request.headers),
        "source": source,
    }
    audit_id = audit.audit_trail.record(policy, result, input_data, meta)
    resp["audit_id"] = audit_id
    return resp
