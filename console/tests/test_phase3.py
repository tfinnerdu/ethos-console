"""Tests for /api/phase3 endpoints — UniData direct query and subroutine call.

Not previously covered: run_colleague_query and call_subroutine let a logged-in
user run arbitrary TCL/UniQuery or an arbitrary subroutine directly against
Colleague with no further restriction — intentional (this is the feature), but
that means the audit trail is the accountability for it. Added in the same
pre-launch audit pass that flagged these two endpoints had no write_event
call at all (test_contracts.py only covers the unconfigured/503 branch).
"""
from unittest.mock import MagicMock

import pytest

from app.database import AuditEntry


@pytest.fixture()
def mock_unidata(app):
    """Replace app.extensions['unidata_client'] with a MagicMock."""
    original = app.extensions.get("unidata_client")
    mock = MagicMock()
    mock.is_configured.return_value = True
    app.extensions["unidata_client"] = mock
    yield mock
    app.extensions["unidata_client"] = original


# ── Colleague Direct Query ────────────────────────────────────────────────────

def test_colleague_query_success(client, mock_unidata):
    mock_unidata.run_command.return_value = "1 record listed"
    r = client.post("/api/phase3/colleague-query", json={"statement": "LIST PERSON SAMPLE 1"})
    assert r.status_code == 200
    assert r.get_json() == {"output": "1 record listed"}


def test_colleague_query_success_emits_audit_event(client, mock_unidata, app):
    mock_unidata.run_command.return_value = "ok"
    client.post("/api/phase3/colleague-query", json={"statement": "LIST PERSON SAMPLE 1"})
    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="call", resource_type="unidata_command",
            resource_id="LIST PERSON SAMPLE 1",
        ).first()
    assert entry is not None
    assert entry.outcome == "success"


def test_colleague_query_failure_emits_audit_event(client, mock_unidata, app):
    mock_unidata.run_command.side_effect = RuntimeError("syntax error")
    r = client.post("/api/phase3/colleague-query", json={"statement": "GARBAGE STATEMENT"})
    assert r.status_code == 500
    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="call", resource_type="unidata_command",
            resource_id="GARBAGE STATEMENT",
        ).first()
    assert entry is not None
    assert entry.outcome == "failure"
    assert "syntax error" in entry.failure_reason


def test_colleague_query_statement_truncated_in_audit_resource_id(client, mock_unidata, app):
    long_statement = "LIST PERSON WITH " + ("X" * 600)
    mock_unidata.run_command.return_value = "ok"
    client.post("/api/phase3/colleague-query", json={"statement": long_statement})
    with app.app_context():
        entry = AuditEntry.query.filter_by(action="call", resource_type="unidata_command").first()
    assert entry is not None
    assert len(entry.resource_id) <= 500


def test_colleague_query_missing_statement_returns_400(client, mock_unidata):
    r = client.post("/api/phase3/colleague-query", json={})
    assert r.status_code == 400
    assert "statement" in r.get_json()["error"]


# ── Subroutine call ───────────────────────────────────────────────────────────

def test_subroutine_success(client, mock_unidata):
    mock_unidata.call_subroutine.return_value = {"args": [{"label": "OUT", "value": "42"}]}
    r = client.post("/api/phase3/subroutine", json={"name": "calc.person", "args": [{"label": "OUT"}]})
    assert r.status_code == 200
    # name is uppercased before being passed through.
    mock_unidata.call_subroutine.assert_called_with("CALC.PERSON", [{"label": "OUT"}])


def test_subroutine_success_emits_audit_event_without_arg_values(client, mock_unidata, app):
    mock_unidata.call_subroutine.return_value = {"args": []}
    client.post("/api/phase3/subroutine", json={
        "name": "calc.person",
        "args": [{"label": "IN", "value": "sensitive-person-id"}],
    })
    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="call", resource_type="unidata_subroutine", resource_id="CALC.PERSON",
        ).first()
    assert entry is not None
    assert entry.outcome == "success"
    assert entry.detail == {"arg_count": 1}
    # The actual argument value must never appear anywhere in the audit row.
    assert "sensitive-person-id" not in str(entry.detail)


def test_subroutine_failure_emits_audit_event(client, mock_unidata, app):
    mock_unidata.call_subroutine.side_effect = RuntimeError("subroutine not found")
    r = client.post("/api/phase3/subroutine", json={"name": "bad.sub", "args": []})
    assert r.status_code == 500
    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="call", resource_type="unidata_subroutine", resource_id="BAD.SUB",
        ).first()
    assert entry is not None
    assert entry.outcome == "failure"
    assert "subroutine not found" in entry.failure_reason


def test_subroutine_missing_name_returns_400(client, mock_unidata):
    r = client.post("/api/phase3/subroutine", json={"args": []})
    assert r.status_code == 400
    assert "name" in r.get_json()["error"]


# ── Other routes ──────────────────────────────────────────────────────────────

def test_list_unidata_files_success(client, mock_unidata):
    mock_unidata.list_files.return_value = ["PERSON", "COURSES"]
    r = client.get("/api/phase3/unidata-files")
    assert r.status_code == 200
    assert r.get_json() == {"items": ["PERSON", "COURSES"]}


def test_list_colleague_files_success(client, mock_unidata):
    mock_unidata.list_files.return_value = ["PERSON"]
    r = client.get("/api/phase3/colleague-files")
    assert r.status_code == 200
    assert r.get_json() == {"items": ["PERSON"]}
