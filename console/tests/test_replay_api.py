"""Tests for /api/replay endpoints."""
from unittest.mock import MagicMock
import pytest
import requests as req_lib


@pytest.fixture()
def mock_conductor(app):
    """Replace app.extensions['conductor_client'] with a MagicMock for one test."""
    original = app.extensions.get("conductor_client")
    mock = MagicMock()
    mock.is_configured.return_value = True
    mock.trigger_workflow.return_value = "wf-id-123"
    app.extensions["conductor_client"] = mock
    yield mock
    if original is not None:
        app.extensions["conductor_client"] = original


@pytest.fixture()
def real_conductor(app):
    """Install a real (non-mocked) ConductorClient — needed to exercise its
    host allow-list for real, since mock_conductor bypasses trigger_workflow
    entirely."""
    from app.conductor_client import ConductorClient
    original = app.extensions.get("conductor_client")
    real = ConductorClient(base_url="https://du-int.doane.edu/prod/conductor", api_key="real-key")
    app.extensions["conductor_client"] = real
    yield real
    if original is not None:
        app.extensions["conductor_client"] = original


# ── fetch ─────────────────────────────────────────────────────────────────────

def test_fetch_missing_message_id_returns_400(client):
    r = client.post("/api/replay/fetch", json={})
    assert r.status_code == 400
    assert "message_id" in r.get_json()["error"]


def test_fetch_non_object_json_body_returns_400_not_500(client):
    # Regression: request.get_json(force=True) on a JSON body that isn't an
    # object (null, a list, a bare scalar) returns None, and calling .get()
    # on None used to raise an unhandled AttributeError -> 500.
    r = client.post("/api/replay/fetch", data="null", content_type="application/json")
    assert r.status_code == 400


def test_trigger_non_object_json_body_returns_400_not_500(client):
    r = client.post("/api/replay/trigger", data="[]", content_type="application/json")
    assert r.status_code == 400


def test_fetch_without_ethos_key_returns_503(client):
    r = client.post("/api/replay/fetch", json={"message_id": "42"})
    assert r.status_code == 503


def test_fetch_message_not_found_returns_404(client, mock_ethos):
    mock_ethos.consume_messages.return_value = []
    r = client.post("/api/replay/fetch", json={"message_id": "42"})
    assert r.status_code == 404


def test_fetch_returns_message_on_success(client, mock_ethos):
    mock_ethos.consume_messages.return_value = [
        {"id": 42, "resource": {"name": "persons", "operation": "updated"}, "content": {}}
    ]
    r = client.post("/api/replay/fetch", json={"message_id": "42"})
    assert r.status_code == 200
    data = r.get_json()
    assert "message" in data
    assert data["message"]["id"] == 42


def test_fetch_passes_correct_last_processed_id(client, mock_ethos):
    mock_ethos.consume_messages.return_value = []
    client.post("/api/replay/fetch", json={"message_id": "10"})
    # message_id=10 → last_processed_id=9
    mock_ethos.consume_messages.assert_called_with(limit=1, last_processed_id=9)


# ── trigger ───────────────────────────────────────────────────────────────────

_VALID_PAYLOAD = {
    "id": "msg-001",
    "resource": {"name": "persons", "operation": "updated"},
    "content": {"id": "abc-123"},
}

def test_trigger_missing_payload_returns_400(client):
    r = client.post("/api/replay/trigger",
                    json={"workflow_name": "wf", "conductor_url": "http://c/"})
    assert r.status_code == 400
    assert "payload" in r.get_json()["error"]


def test_trigger_missing_workflow_name_returns_400(client):
    r = client.post("/api/replay/trigger",
                    json={"payload": _VALID_PAYLOAD, "conductor_url": "http://c/"})
    assert r.status_code == 400
    assert "workflow_name" in r.get_json()["error"]


def test_trigger_missing_conductor_url_returns_400(client, app):
    app.config["CONDUCTOR_URL"] = ""
    r = client.post("/api/replay/trigger",
                    json={"payload": _VALID_PAYLOAD, "workflow_name": "wf"})
    assert r.status_code == 400
    assert "conductor_url" in r.get_json()["error"]


def test_trigger_rejects_unlisted_conductor_host(client, app, real_conductor):
    # Regression: an operator-supplied conductor_url override used to be
    # forwarded (with the real API key attached) to any host, no allow-list.
    app.config["CONDUCTOR_URL"] = "https://du-int.doane.edu/prod/conductor"

    r = client.post("/api/replay/trigger", json={
        "payload": _VALID_PAYLOAD,
        "workflow_name": "my-workflow",
        "conductor_url": "https://attacker.example.com",
    })

    assert r.status_code == 400
    assert "not allow-listed" in r.get_json()["error"]


def test_trigger_allows_configured_conductor_host_with_real_client(client, app, real_conductor, monkeypatch):
    app.config["CONDUCTOR_URL"] = "https://du-int.doane.edu/prod/conductor"
    fake_response = MagicMock()
    fake_response.text = '"wf-real-1"'
    fake_response.raise_for_status.return_value = None
    monkeypatch.setattr("app.conductor_client.requests.post", lambda *a, **k: fake_response)

    r = client.post("/api/replay/trigger", json={
        "payload": _VALID_PAYLOAD,
        "workflow_name": "my-workflow",
    })

    assert r.status_code == 200
    assert r.get_json()["workflow_id"] == "wf-real-1"


def test_trigger_success_returns_workflow_id(client, app, mock_conductor):
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_conductor.trigger_workflow.return_value = "wf-id-123"

    r = client.post("/api/replay/trigger", json={
        "payload": _VALID_PAYLOAD,
        "workflow_name": "my-workflow",
    })

    assert r.status_code == 200
    data = r.get_json()
    assert data["outcome"] == "success"
    assert data["workflow_id"] == "wf-id-123"
    assert "conductor_workflow_url" in data


def test_trigger_http_error_returns_502(client, app, mock_conductor):
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_conductor.trigger_workflow.side_effect = req_lib.HTTPError("503 Server Error")

    r = client.post("/api/replay/trigger", json={
        "payload": _VALID_PAYLOAD,
        "workflow_name": "my-workflow",
    })

    assert r.status_code == 502
    assert r.get_json()["outcome"] == "error"


def test_trigger_persists_history_on_success(client, app, mock_conductor):
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_conductor.trigger_workflow.return_value = "wf-abc"

    client.post("/api/replay/trigger", json={
        "payload": _VALID_PAYLOAD,
        "workflow_name": "my-workflow",
    })

    r = client.get("/api/replay/history")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(i["outcome"] == "success" and i["resource_name"] == "persons"
               for i in items)


def test_trigger_persists_history_on_error(client, app, mock_conductor):
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_conductor.trigger_workflow.side_effect = req_lib.HTTPError("404")

    client.post("/api/replay/trigger", json={
        "payload": _VALID_PAYLOAD,
        "workflow_name": "error-workflow",
    })

    r = client.get("/api/replay/history")
    items = r.get_json()["items"]
    assert any(i["outcome"] == "error" for i in items)


def test_trigger_success_emits_audit_event(client, app, mock_conductor):
    from app.database import AuditEntry
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_conductor.trigger_workflow.return_value = "wf-audit-1"

    client.post("/api/replay/trigger", json={
        "payload": _VALID_PAYLOAD,
        "workflow_name": "my-workflow",
    })

    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="trigger", resource_id="wf-audit-1",
        ).first()
    assert entry is not None
    assert entry.outcome == "success"


def test_trigger_failure_emits_audit_event(client, app, mock_conductor):
    from app.database import AuditEntry
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_conductor.trigger_workflow.side_effect = req_lib.HTTPError("503 Server Error")

    client.post("/api/replay/trigger", json={
        "payload": _VALID_PAYLOAD,
        "workflow_name": "audit-failure-workflow",
    })

    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="trigger", resource_id="audit-failure-workflow",
        ).first()
    assert entry is not None
    assert entry.outcome == "failure"


# ── history ───────────────────────────────────────────────────────────────────

def test_history_returns_200(client):
    r = client.get("/api/replay/history")
    assert r.status_code == 200


def test_history_shape(client):
    data = client.get("/api/replay/history").get_json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "pages" in data


def test_history_pagination(client, app, mock_conductor):
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_conductor.trigger_workflow.return_value = "wf-pg"

    for i in range(3):
        client.post("/api/replay/trigger", json={
            "payload": {**_VALID_PAYLOAD, "id": f"msg-{i}"},
            "workflow_name": "wf",
        })

    data = client.get("/api/replay/history?per_page=2").get_json()
    assert len(data["items"]) <= 2
    assert data["total"] >= 3
