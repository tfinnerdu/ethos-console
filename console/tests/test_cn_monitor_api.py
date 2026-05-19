"""Tests for /api/cn endpoints.

All CNM HTTP calls are mocked — no live CNM service needed.
Tests cover: 503 setup guide, 200 happy paths, 502 on upstream error.
"""
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture()
def cnm_client(app):
    """Configure app with a CNM_BASE_URL and inject a mock CnmClient."""
    original_url = app.config.get("CNM_BASE_URL", "")
    original_key = app.config.get("CNM_API_KEY", "")
    app.config["CNM_BASE_URL"] = "http://cnm-test"
    app.config["CNM_API_KEY"] = ""

    mock = MagicMock()
    mock.is_configured.return_value = True
    mock.get_health.return_value = {"status": "ok", "service": "cnm-api", "version": "1.0.0", "uptime_seconds": 300}
    mock.get_notifications.return_value = [
        {"id": "cn-1", "resourceName": "persons", "description": "Person updated",
         "status": "Enabled", "hasParagraph": False, "lastModified": "2026-05-01T12:00:00Z"},
        {"id": "cn-2", "resourceName": "courses", "description": "Course created",
         "status": "Disabled", "hasParagraph": True, "lastModified": "2026-05-02T08:00:00Z"},
    ]
    mock.get_notification.return_value = {
        "id": "cn-1", "resourceName": "persons", "description": "Person updated",
        "status": "Enabled", "paragraphCode": None, "processCode": "SAVEPERSON",
        "parameters": ["ID"], "edpsRules": [], "lastModified": "2026-05-01T12:00:00Z",
    }
    mock.get_paragraph.return_value = {"code": "PARA1", "source": "paragraph text"}
    mock.get_cn_history.return_value = [
        {"auditId": 1, "timestamp": "2026-05-01T12:00:00Z", "userId": "u1",
         "userDisplayName": "Alice", "action": "View", "targetType": "ChangeNotification",
         "targetIdentifier": "cn-1", "outcome": "Success", "correlationId": "abc"}
    ]
    mock.get_diagnostics.return_value = {
        "subscribedNotPublished": ["events"],
        "publishedNotSubscribed": ["sections"],
        "aligned": ["persons", "courses"],
        "totalSubscribed": 3,
        "totalPublished": 3,
    }
    mock.get_audit_log.return_value = {
        "items": [
            {"auditId": 1, "timestamp": "2026-05-01T12:00:00Z", "userId": "u1",
             "userDisplayName": "Alice", "action": "View", "targetType": "ChangeNotification",
             "targetIdentifier": "cn-1", "outcome": "Success", "correlationId": "abc",
             "beforeState": None, "afterState": None, "failureReason": None, "sourceIp": None}
        ],
        "totalCount": 1, "page": 1, "pageSize": 50,
    }

    with patch("app.routes.cn_monitor.CnmClient", return_value=mock):
        yield app.test_client(), mock

    app.config["CNM_BASE_URL"] = original_url
    app.config["CNM_API_KEY"] = original_key


# ── 503 setup guide (no CNM_BASE_URL) ────────────────────────────────────────

def test_health_503_when_not_configured(client):
    r = client.get("/api/cn/health")
    assert r.status_code == 503
    data = r.get_json()
    assert "error" in data
    assert "setup" in data
    assert "CNM_BASE_URL" in data["setup"]


def test_notifications_503_when_not_configured(client):
    r = client.get("/api/cn/notifications")
    assert r.status_code == 503


def test_diagnostics_503_when_not_configured(client):
    r = client.get("/api/cn/diagnostics")
    assert r.status_code == 503


def test_audit_log_503_when_not_configured(client):
    r = client.get("/api/cn/audit-log")
    assert r.status_code == 503


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_200(cnm_client):
    tc, _ = cnm_client
    r = tc.get("/api/cn/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "cnm-api"


def test_health_502_on_upstream_error(app):
    original = app.config.get("CNM_BASE_URL", "")
    app.config["CNM_BASE_URL"] = "http://cnm-test"
    mock = MagicMock()
    mock.is_configured.return_value = True
    mock.get_health.side_effect = Exception("connection refused")
    with patch("app.routes.cn_monitor.CnmClient", return_value=mock):
        r = app.test_client().get("/api/cn/health")
    assert r.status_code == 502
    app.config["CNM_BASE_URL"] = original


# ── Notifications list ────────────────────────────────────────────────────────

def test_notifications_200(cnm_client):
    tc, _ = cnm_client
    r = tc.get("/api/cn/notifications")
    assert r.status_code == 200


def test_notifications_has_items_and_total(cnm_client):
    tc, _ = cnm_client
    data = tc.get("/api/cn/notifications").get_json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 2


def test_notifications_item_shape(cnm_client):
    tc, _ = cnm_client
    item = tc.get("/api/cn/notifications").get_json()["items"][0]
    assert "id" in item
    assert "resourceName" in item
    assert "status" in item
    assert "hasParagraph" in item


def test_notifications_passes_resource_filter(cnm_client):
    tc, mock = cnm_client
    tc.get("/api/cn/notifications?resource=persons")
    mock.get_notifications.assert_called_with(resource="persons", status=None)


def test_notifications_passes_status_filter(cnm_client):
    tc, mock = cnm_client
    tc.get("/api/cn/notifications?status=Enabled")
    mock.get_notifications.assert_called_with(resource=None, status="Enabled")


# ── Notification detail ───────────────────────────────────────────────────────

def test_notification_detail_200(cnm_client):
    tc, _ = cnm_client
    r = tc.get("/api/cn/notifications/cn-1")
    assert r.status_code == 200
    data = r.get_json()
    assert data["id"] == "cn-1"
    assert "parameters" in data
    assert "edpsRules" in data


def test_notification_detail_404_propagated(app):
    original = app.config.get("CNM_BASE_URL", "")
    app.config["CNM_BASE_URL"] = "http://cnm-test"
    mock = MagicMock()
    mock.is_configured.return_value = True
    mock.get_notification.side_effect = Exception("404 Not Found")
    with patch("app.routes.cn_monitor.CnmClient", return_value=mock):
        r = app.test_client().get("/api/cn/notifications/bad-id")
    assert r.status_code == 404
    app.config["CNM_BASE_URL"] = original


# ── Paragraph ─────────────────────────────────────────────────────────────────

def test_paragraph_200(cnm_client):
    tc, _ = cnm_client
    r = tc.get("/api/cn/notifications/cn-1/paragraph")
    assert r.status_code == 200
    data = r.get_json()
    assert "code" in data
    assert "source" in data


# ── CN history ────────────────────────────────────────────────────────────────

def test_cn_history_200(cnm_client):
    tc, _ = cnm_client
    r = tc.get("/api/cn/notifications/cn-1/history")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data
    assert len(data["items"]) == 1


# ── Diagnostics ───────────────────────────────────────────────────────────────

def test_diagnostics_200(cnm_client):
    tc, _ = cnm_client
    r = tc.get("/api/cn/diagnostics")
    assert r.status_code == 200


def test_diagnostics_shape(cnm_client):
    tc, _ = cnm_client
    data = tc.get("/api/cn/diagnostics").get_json()
    assert "subscribedNotPublished" in data
    assert "publishedNotSubscribed" in data
    assert "aligned" in data
    assert "totalSubscribed" in data
    assert "totalPublished" in data


def test_diagnostics_502_on_upstream_error(app):
    original = app.config.get("CNM_BASE_URL", "")
    app.config["CNM_BASE_URL"] = "http://cnm-test"
    mock = MagicMock()
    mock.is_configured.return_value = True
    mock.get_diagnostics.side_effect = Exception("timeout")
    with patch("app.routes.cn_monitor.CnmClient", return_value=mock):
        r = app.test_client().get("/api/cn/diagnostics")
    assert r.status_code == 502
    app.config["CNM_BASE_URL"] = original


# ── Audit log ─────────────────────────────────────────────────────────────────

def test_audit_log_200(cnm_client):
    tc, _ = cnm_client
    r = tc.get("/api/cn/audit-log")
    assert r.status_code == 200


def test_audit_log_shape(cnm_client):
    tc, _ = cnm_client
    data = tc.get("/api/cn/audit-log").get_json()
    assert "items" in data
    assert "totalCount" in data
    assert "page" in data
    assert "pageSize" in data


def test_audit_log_passes_pagination(cnm_client):
    tc, mock = cnm_client
    tc.get("/api/cn/audit-log?page=2&pageSize=25")
    mock.get_audit_log.assert_called_with(page=2, page_size=25, user_id=None, target_identifier=None)


def test_audit_log_passes_target_filter(cnm_client):
    tc, mock = cnm_client
    tc.get("/api/cn/audit-log?targetIdentifier=cn-1")
    mock.get_audit_log.assert_called_with(page=1, page_size=50, user_id=None, target_identifier="cn-1")


# ── Push change notifications ─────────────────────────────────────────────────

@pytest.fixture()
def push_client(app):
    """Configure app with a mocked EthosClient that supports push methods."""
    original = app.extensions.get("ethos_client")
    mock = MagicMock()
    mock.is_configured.return_value = True
    mock.get_resource_by_id.return_value = (
        {"id": "fee12eb6-dae1-456b-a7c4-063458617478", "firstName": "Alice"},
        "application/vnd.hedtech.integration.v8+json",
    )
    mock.publish_notification.return_value = {}
    app.extensions["ethos_client"] = mock
    yield app.test_client(), mock
    app.extensions["ethos_client"] = original


def test_push_503_when_ethos_not_configured(client):
    r = client.post("/api/cn/push", json={"resource_name": "persons", "guids": ["abc"]})
    assert r.status_code == 503
    data = r.get_json()
    assert "error" in data
    assert "setup" in data


def test_push_400_missing_resource_name(push_client):
    tc, _ = push_client
    r = tc.post("/api/cn/push", json={"guids": ["abc"]})
    assert r.status_code == 400
    assert "resource_name" in r.get_json()["error"]


def test_push_400_missing_guids(push_client):
    tc, _ = push_client
    r = tc.post("/api/cn/push", json={"resource_name": "persons", "guids": []})
    assert r.status_code == 400
    assert "guid" in r.get_json()["error"]


def test_push_200_returns_results(push_client):
    tc, _ = push_client
    r = tc.post("/api/cn/push", json={
        "resource_name": "persons",
        "operation": "replaced",
        "guids": ["fee12eb6-dae1-456b-a7c4-063458617478"],
    })
    assert r.status_code == 200
    data = r.get_json()
    assert "results" in data
    assert len(data["results"]) == 1


def test_push_success_result_shape(push_client):
    tc, _ = push_client
    data = tc.post("/api/cn/push", json={
        "resource_name": "persons",
        "guids": ["fee12eb6-dae1-456b-a7c4-063458617478"],
    }).get_json()
    result = data["results"][0]
    assert result["status"] == "success"
    assert result["guid"] == "fee12eb6-dae1-456b-a7c4-063458617478"
    assert "version" in result


def test_push_calls_get_resource_by_id(push_client):
    tc, mock = push_client
    tc.post("/api/cn/push", json={"resource_name": "persons", "guids": ["abc-123"]})
    mock.get_resource_by_id.assert_called_with("persons", "abc-123")


def test_push_calls_publish_notification(push_client):
    tc, mock = push_client
    tc.post("/api/cn/push", json={
        "resource_name": "persons", "operation": "created", "guids": ["abc-123"],
    })
    call_args = mock.publish_notification.call_args[0][0]
    assert call_args["resource"]["name"] == "persons"
    assert call_args["resource"]["id"] == "abc-123"
    assert call_args["operation"] == "created"
    assert call_args["contentType"] == "resource-representation"


def test_push_error_result_when_upstream_fails(app):
    original = app.extensions.get("ethos_client")
    mock = MagicMock()
    mock.is_configured.return_value = True
    mock.get_resource_by_id.side_effect = Exception("404 Not Found")
    app.extensions["ethos_client"] = mock
    r = app.test_client().post("/api/cn/push", json={
        "resource_name": "persons", "guids": ["bad-guid"],
    })
    assert r.status_code == 200
    result = r.get_json()["results"][0]
    assert result["status"] == "error"
    assert "404" in result["error"]
    app.extensions["ethos_client"] = original


def test_push_partial_results_on_mixed_outcomes(app):
    """Some GUIDs succeed, others fail — all returned in results list."""
    original = app.extensions.get("ethos_client")
    mock = MagicMock()
    mock.is_configured.return_value = True
    call_count = [0]

    def side_effect(resource, guid):
        call_count[0] += 1
        if call_count[0] % 2 == 0:
            raise Exception("upstream error")
        return {"id": guid}, "application/json"

    mock.get_resource_by_id.side_effect = side_effect
    mock.publish_notification.return_value = {}
    app.extensions["ethos_client"] = mock

    r = app.test_client().post("/api/cn/push", json={
        "resource_name": "persons",
        "guids": ["guid-1", "guid-2", "guid-3"],
    })
    assert r.status_code == 200
    results = r.get_json()["results"]
    assert len(results) == 3
    statuses = [res["status"] for res in results]
    assert "success" in statuses
    assert "error" in statuses

    app.extensions["ethos_client"] = original
