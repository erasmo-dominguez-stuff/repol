"""Audit trail query endpoints."""

from fastapi import APIRouter, HTTPException, Query

from .. import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def get_audit(
    limit: int = Query(50, ge=1, le=500),
    policy: str | None = Query(None),
    decision: str | None = Query(None),
    since: str | None = Query(None, description="ISO timestamp"),
    environment: str | None = Query(None),
):
    """Query audit events with optional filters."""
    return audit.query(
        limit=limit,
        policy=policy,
        decision=decision,
        since=since,
        environment=environment,
    )


@router.get("/{event_id}")
async def get_audit_event(event_id: str):
    """Retrieve a single audit event by ID."""
    event = audit.get_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return event
