"""Adapter: SQLite AuditTrail (hexagonal, SOLID)."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import AUDIT_DB as _AUDIT_DB_STR
from ..core.audit_trail import AuditTrail


class SQLiteAuditTrail(AuditTrail):
    def __init__(self):
        requested_path = Path(_AUDIT_DB_STR)
        self.db_path = self._resolve_db_path(requested_path)
        self._ensure_schema()

    def _resolve_db_path(self, requested_path: Path) -> Path:
        try:
            requested_path.parent.mkdir(parents=True, exist_ok=True)
            return requested_path
        except PermissionError:
            fallback = Path.cwd() / ".data" / "audit.db"
            fallback.parent.mkdir(parents=True, exist_ok=True)
            return fallback

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    policy TEXT NOT NULL,
                    allow INTEGER NOT NULL,
                    decision TEXT NOT NULL,
                    input TEXT NOT NULL,
                    meta TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_policy_ts ON audit_events(policy, timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_allow_ts ON audit_events(allow, timestamp)"
            )

    def record(self, policy: str, result: dict, input_data: dict, meta: dict) -> str:
        audit_id = str(uuid.uuid4())
        allow = bool(result.get("allow", False))
        payload = {
            "allow": allow,
            "violations": result.get("violations", []),
        }
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_events(id, timestamp, policy, allow, decision, input, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    now,
                    policy,
                    1 if allow else 0,
                    json.dumps(payload),
                    json.dumps(input_data),
                    json.dumps(meta or {}),
                ),
            )
        return audit_id

    def query(self, **filters) -> list:
        clauses = []
        values = []

        if filters.get("policy"):
            clauses.append("policy = ?")
            values.append(filters["policy"])

        if "decision" in filters and filters["decision"] is not None:
            decision = filters["decision"]
            if isinstance(decision, str):
                allow = decision.lower() in {"allow", "allowed", "true", "1", "approved"}
            else:
                allow = bool(decision)
            clauses.append("allow = ?")
            values.append(1 if allow else 0)

        if filters.get("since"):
            clauses.append("timestamp >= ?")
            values.append(filters["since"])

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit = int(filters.get("limit", 100))
        limit = max(1, min(limit, 500))

        query = f"""
            SELECT id, timestamp, policy, allow, decision, input, meta
            FROM audit_events
            {where}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        values.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, values).fetchall()

        events = []
        for row in rows:
            decision = json.loads(row["decision"])
            item = {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "policy": row["policy"],
                "allow": bool(row["allow"]),
                "violations": decision.get("violations", []),
                "input": json.loads(row["input"]),
                "meta": json.loads(row["meta"]),
            }
            events.append(item)
        return events
