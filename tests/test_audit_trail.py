from app.adapters.sqlite_audit_trail import SQLiteAuditTrail

def test_audit_trail_record_and_query():
    audit = SQLiteAuditTrail()
    audit_id = audit.record("deploy", {"allow": True}, {"ref": "main"}, {"source": "test"})
    assert isinstance(audit_id, str)
    events = audit.query(policy="deploy")
    assert isinstance(events, list)
