"""
AuditTrail factory — selects the correct adapter based on configuration.

This module provides a single `audit_trail` instance, which is injected everywhere.
Implements the factory pattern to select the backend (SQLite, Cosmos, etc).
"""

from .core.audit_trail import AuditTrail
from .adapters.sqlite_audit_trail import SQLiteAuditTrail
from .adapters.env_config import EnvConfig
try:
    from .adapters.cosmos_audit_trail import CosmosAuditTrail
except ImportError:
    CosmosAuditTrail = None

def get_audit_trail() -> AuditTrail:
    config = EnvConfig()
    backend = config.get("AUDIT_BACKEND", "sqlite").lower()
    if backend == "cosmos" and CosmosAuditTrail:
        conn_str = config.get("COSMOS_CONN_STR", "mongodb://cosmosdb:10255/?ssl=true&replicaSet=globaldb")
        return CosmosAuditTrail(conn_str)
    return SQLiteAuditTrail()

# The single injected instance used everywhere
audit_trail: AuditTrail = get_audit_trail()
