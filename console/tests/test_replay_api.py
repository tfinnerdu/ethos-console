"""Tests for /api/replay endpoints."""
from unittest.mock import patch, MagicMock
import requests as req_lib


# ── fetch ─────────────────────────────────────────────────────────────────────

def test_fetch_missing_message_id_returns_400(client):
    r = client.post("/api/replay/fetch", json={})
    assert r.status_code == 400
    assert "message_id" in r.get_json()["error"]


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


def test_trigger_success_returns_workflow_id(client, app):
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_resp = MagicMock()
    mock_resp.text = '"wf-id-123"'
    mock_resp.raise_for_status = MagicMock()

    with patch("app.routes.replay.requests.post", return_value=mock_resp):
        r = client.post("/api/replay/trigger", json={
            "payload": _VALID_PAYLOAD,
            "workflow_name": "my-workflow",
        })

    assert r.status_code == 200
    data = r.get_json()
    assert data["outcome"] == "success"
    assert data["workflow_id"] == "wf-id-123"
    assert "conductor_workflow_url" in data


def test_trigger_http_error_returns_502(client, app):
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req_lib.HTTPError("503 Server Error")

    with patch("app.routes.replay.requests.post", return_value=mock_resp):
        r = client.post("/api/replay/trigger", json={
            "payload": _VALID_PAYLOAD,
            "workflow_name": "my-workflow",
        })

    assert r.status_code == 502
    assert r.get_json()["outcome"] == "error"


def test_trigger_persists_history_on_success(client, app):
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_resp = MagicMock()
    mock_resp.text = '"wf-abc"'
    mock_resp.raise_for_status = MagicMock()

    with patch("app.routes.replay.requests.post", return_value=mock_resp):
        client.post("/api/replay/trigger", json={
            "payload": _VALID_PAYLOAD,
            "workflow_name": "my-workflow",
        })

    r = client.get("/api/replay/history")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(i["outcome"] == "success" and i["resource_name"] == "persons"
               for i in items)


def test_trigger_persists_history_on_error(client, app):
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req_lib.HTTPError("404")

    with patch("app.routes.replay.requests.post", return_value=mock_resp):
        client.post("/api/replay/trigger", json={
            "payload": _VALID_PAYLOAD,
            "workflow_name": "error-workflow",
        })

    r = client.get("/api/replay/history")
    items = r.get_json()["items"]
    assert any(i["outcome"] == "error" for i in items)


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


def test_history_pagination(client, app):
    app.config["CONDUCTOR_URL"] = "http://conductor/"
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.text = '"wf-pg"'

    with patch("app.routes.replay.requests.post", return_value=mock_resp):
        for i in range(3):
            client.post("/api/replay/trigger", json={
                "payload": {**_VALID_PAYLOAD, "id": f"msg-{i}"},
                "workflow_name": "wf",
            })

    data = client.get("/api/replay/history?per_page=2").get_json()
    assert len(data["items"]) <= 2
    assert data["total"] >= 3
