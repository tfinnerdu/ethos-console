"""Tests for /api/colleague endpoints — Colleague Web API CTX transaction
caller, event-configurations, about, and metadata routes.

Not previously covered: this blueprint (app/routes/colleague_api.py) was
entirely absent from docs/test-coverage-classification.md and had zero
route-level tests (flagged as a CRITICAL gap by the standards audit).
"""
from unittest.mock import MagicMock

import pytest

from app.database import AuditEntry


@pytest.fixture()
def mock_colleague_api(app):
    """Replace app.extensions['colleague_api_client'] with a MagicMock."""
    original = app.extensions.get("colleague_api_client")
    mock = MagicMock()
    mock.is_configured.return_value = True
    app.extensions["colleague_api_client"] = mock
    yield mock
    app.extensions["colleague_api_client"] = original


# ── Not configured (503) ─────────────────────────────────────────────────────

def test_about_not_configured_returns_503(client):
    r = client.get("/api/colleague/about")
    assert r.status_code == 503
    data = r.get_json()
    assert "error" in data
    assert "setup" in data


def test_event_configs_not_configured_returns_503(client):
    r = client.get("/api/colleague/event-configurations")
    assert r.status_code == 503


def test_transaction_not_configured_returns_503(client):
    r = client.post("/api/colleague/transaction", json={"transactionId": "GET.PERSON"})
    assert r.status_code == 503


def test_metadata_not_configured_returns_503(client):
    r = client.get("/api/colleague/metadata/person/schema")
    assert r.status_code == 503


# ── Configured (200 / real calls via mock) ───────────────────────────────────

def test_about_returns_client_payload(client, mock_colleague_api):
    mock_colleague_api.get_about.return_value = {"version": "1.2.3"}
    r = client.get("/api/colleague/about")
    assert r.status_code == 200
    assert r.get_json() == {"version": "1.2.3"}


def test_about_client_exception_returns_500(client, mock_colleague_api):
    mock_colleague_api.get_about.side_effect = RuntimeError("upstream down")
    r = client.get("/api/colleague/about")
    assert r.status_code == 500
    assert "upstream down" in r.get_json()["error"]


def test_event_configs_passes_resource_name(client, mock_colleague_api):
    mock_colleague_api.get_event_configurations.return_value = [{"resourceName": "persons"}]
    r = client.get("/api/colleague/event-configurations?resourceName=persons")
    assert r.status_code == 200
    # ethos-console's own ?resourceName= query param is this route's external
    # contract and is unchanged — it's the client's outgoing param to the
    # real Colleague Web API that was wrong (see colleague_api_client.py).
    mock_colleague_api.get_event_configurations.assert_called_with(resource="persons")


def test_event_configs_non_list_response_coerced_to_empty_list(client, mock_colleague_api):
    mock_colleague_api.get_event_configurations.return_value = {"not": "a list"}
    r = client.get("/api/colleague/event-configurations")
    assert r.status_code == 200
    assert r.get_json() == []


def test_transaction_missing_id_returns_400(client, mock_colleague_api):
    r = client.post("/api/colleague/transaction", json={})
    assert r.status_code == 400
    assert "transactionId" in r.get_json()["error"]


def test_transaction_non_object_json_body_returns_400_not_500(client, mock_colleague_api):
    r = client.post(
        "/api/colleague/transaction", data="null", content_type="application/json",
    )
    assert r.status_code == 400


def test_transaction_success(client, mock_colleague_api):
    mock_colleague_api.call_transaction.return_value = {"result": "ok"}
    r = client.post("/api/colleague/transaction", json={
        "transactionId": "get.person.info", "payload": {"personId": "1001"},
    })
    assert r.status_code == 200
    assert r.get_json() == {"result": "ok"}
    # transactionId is uppercased before being passed through.
    mock_colleague_api.call_transaction.assert_called_with("GET.PERSON.INFO", {"personId": "1001"})


def test_transaction_success_emits_audit_event(client, mock_colleague_api, app):
    mock_colleague_api.call_transaction.return_value = {"result": "ok"}
    client.post("/api/colleague/transaction", json={"transactionId": "get.person.info"})
    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="call", resource_type="colleague_ctx_transaction",
            resource_id="GET.PERSON.INFO",
        ).first()
    assert entry is not None
    assert entry.outcome == "success"


def test_transaction_failure_emits_audit_event(client, mock_colleague_api, app):
    mock_colleague_api.call_transaction.side_effect = RuntimeError("transaction rejected")
    r = client.post("/api/colleague/transaction", json={"transactionId": "get.person.fail"})
    assert r.status_code == 500
    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="call", resource_type="colleague_ctx_transaction",
            resource_id="GET.PERSON.FAIL",
        ).first()
    assert entry is not None
    assert entry.outcome == "failure"
    assert "transaction rejected" in entry.failure_reason


def test_metadata_returns_client_payload(client, mock_colleague_api):
    mock_colleague_api.get_metadata_manifest.return_value = {"ApiDomain": "person"}
    r = client.get("/api/colleague/metadata/person/schema")
    assert r.status_code == 200
    mock_colleague_api.get_metadata_manifest.assert_called_with("person", "schema")
