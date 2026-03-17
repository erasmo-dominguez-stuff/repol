"""Adapter: CosmosAuditTrail (hexagonal, SOLID).

Implements AuditTrail interface using Azure Cosmos DB (Mongo API or SQL API).
"""
from ..core.audit_trail import AuditTrail
import uuid
from datetime import datetime, timezone
import json

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None

class CosmosAuditTrail(AuditTrail):
    def __init__(self, conn_str, db_name="auditdb", collection="audit_events"):
        if MongoClient is None:
            raise ImportError("pymongo is required for CosmosAuditTrail")
        self.client = MongoClient(conn_str)
        self.db = self.client[db_name]
        self.collection = self.db[collection]

    def record(self, policy: str, result: dict, input_data: dict, meta: dict) -> str:
        audit_id = str(uuid.uuid4())
        doc = {
            "_id": audit_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "policy": policy,
            "decision": json.dumps(result),
            "input": json.dumps(input_data),
            "meta": json.dumps(meta),
        }
        self.collection.insert_one(doc)
        return audit_id

    def query(self, **filters) -> list:
        return list(self.collection.find(filters))
