"""Audit trail — records every policy evaluation for traceability."""

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

AUDIT_DB = Path(os.getenv("AUDIT_DB", "/data/audit.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    id          TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    policy      TEXT NOT NULL,
    decision    TEXT NOT NULL,
    violations  TEXT NOT NULL DEFAULT '[]',
    input_hash  TEXT,
    actor       TEXT,
    source      TEXT,
    environment TEXT,
    ref         TEXT,
    meta        TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_ts       ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_policy   ON audit_events(policy);
CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit_events(decision);
"""


@contextmanager
def _conn():
    AUDIT_DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(AUDIT_DB))
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()


def _deserialize_row(row) -> dict:
    """Convert a sqlite3.Row to a dict with parsed JSON fields."""
    d = dict(row)
    d["violations"] = json.loads(d["violations"])
    d["meta"] = json.loads(d["meta"])
    return d


def init_db():
    with _conn() as db:
        db.executescript(_SCHEMA)


def record(
    *,
    policy: str,
    decision: bool,
    violations: list,
    input_data: dict,
    actor: str = "",
    source: str = "",
) -> dict:
    """Write an audit event and return it."""
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    environment = input_data.get("environment", "")
    ref = input_data.get("ref", "") or input_data.get("base_ref", "")

    input_hash = hashlib.sha256(
        json.dumps(input_data, sort_keys=True).encode()
    ).hexdigest()[:16]

    meta = {
        "head_ref": input_data.get("head_ref", ""),
        "approvers": (input_data.get("workflow_meta") or {}).get("approvers", []),
    }

    row = {
        "id": event_id,
        "timestamp": now,
        "policy": policy,
        "decision": "allow" if decision else "deny",
        "violations": json.dumps(violations),
        "input_hash": input_hash,
        "actor": actor,
        "source": source,
        "environment": environment,
        "ref": ref,
        "meta": json.dumps(meta),
    }

    with _conn() as db:
        db.execute(
            """INSERT INTO audit_events
               (id, timestamp, policy, decision, violations, input_hash,
                actor, source, environment, ref, meta)
               VALUES (:id, :timestamp, :policy, :decision, :violations,
                       :input_hash, :actor, :source, :environment, :ref, :meta)""",
            row,
        )

    row["violations"] = violations
    row["meta"] = meta
    return row


def get_by_id(event_id: str) -> dict | None:
    """Retrieve a single audit event by ID."""
    with _conn() as db:
        row = db.execute(
            "SELECT * FROM audit_events WHERE id = :id", {"id": event_id}
        ).fetchone()
    if not row:
        return None
    return _deserialize_row(row)


def query(
    *,
    limit: int = 50,
    policy: str | None = None,
    decision: str | None = None,
    since: str | None = None,
    environment: str | None = None,
) -> list[dict]:
    """Query audit events with optional filters."""
    clauses = []
    params: dict = {}

    if policy:
        clauses.append("policy = :policy")
        params["policy"] = policy
    if decision:
        clauses.append("decision = :decision")
        params["decision"] = decision
    if since:
        clauses.append("timestamp >= :since")
        params["since"] = since
    if environment:
        clauses.append("environment = :environment")
        params["environment"] = environment

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params["limit"] = min(limit, 500)

    with _conn() as db:
        rows = db.execute(
            f"SELECT * FROM audit_events {where} ORDER BY timestamp DESC LIMIT :limit",
            params,
        ).fetchall()

    return [_deserialize_row(r) for r in rows]
