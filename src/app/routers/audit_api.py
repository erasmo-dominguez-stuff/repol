from fastapi import APIRouter

from .. import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def audit_query(
    policy: str | None = None,
    decision: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list:
    return audit.audit_trail.query(policy=policy, decision=decision, since=since, limit=limit)


@router.get("/summary")
async def audit_summary() -> dict:
    events = audit.audit_trail.query(limit=500)
    by_decision = {"allow": 0, "deny": 0}
    by_policy = {}

    for event in events:
        allow = bool(event.get("allow", False))
        by_decision["allow" if allow else "deny"] += 1
        key = event.get("policy", "unknown")
        by_policy[key] = by_policy.get(key, 0) + 1

    return {"total": len(events), "by_decision": by_decision, "by_policy": by_policy}


@router.get("/{audit_id}")
async def audit_get(audit_id: str) -> dict:
    events = audit.audit_trail.query(limit=500)
    for event in events:
        if event.get("id") == audit_id:
            return event
    return {}
