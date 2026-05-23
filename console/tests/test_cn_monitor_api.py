"""Tests for /api/cn endpoints (post-fold — no CnmClient proxy hop)."""
from unittest.mock import MagicMock
import pytest

from app.audit import Action, write_event
from app.database import AuditEntry


@pytest.fixture()
def cn_repo(app):
    """Inject a MagicMock CnRepository for one test."""
    original = app.extensions.get("cn_repository")
    mock = MagicMock()
    mock.is_configured.return_value = True
    mock.get_health.return_value = {
        "status": "ok",
        "service": "ethos-console.cn",
        "colleague_api_configured": False,
    }
    mock.get_notifications.return_value = [
        {"id": "cn-1", "resourceName": "persons",  "status": "Enabled",
         "hasParagraph": False, "lastModified": "2026-05-01T12:00:00Z"},
        {"id": "cn-2", "resourceName": "courses",  "status": "Disabled",
         "hasParagraph": True,  "lastModified": "2026-05-02T08:00:00Z"},
    ]
    mock.get_notification.return_value = {
        "id": "cn-1", "resourceName": "persons", "status": "Enabled",
        "paragraphCode": None, "processCode": "SAVEPERSON",
        "parameters": ["ID"], "edpsRules": [],
    }
    mock.get_paragraph.return_value = {"code": "PARA1", "source": "paragraph text"}
    mock.get_diagnostics.return_value = {
        "aligned": ["persons", "courses"],
        "subscribedNotPublished": ["events"],
        "publishedNotSubscribed": ["sections"],
        "totalSubscribed": 3,
        "totalPublished": 3,
    }
    app.extensions["cn_repository"] = mock
    yield app.test_client(), mock
    if original is not None:
        app.extensions["cn_repository"] = original


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_200(cn_repo):
    tc, _ = cn_repo
    r = tc.get("/api/cn/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


# ── Notifications list ────────────────────────────────────────────────────────

def test_notifications_200(cn_repo):
    tc, _ = cn_repo
    r = tc.get("/api/cn/notifications")
    assert r.status_code == 200


def test_notifications_has_items_and_total(cn_repo):
    tc, _ = cn_repo
    data = tc.get("/api/cn/notifications").get_json()
    assert "items" in data
    assert data["total"] == 2


def test_notifications_item_shape(cn_repo):
    tc, _ = cn_repo
    item = tc.get("/api/cn/notifications").get_json()["items"][0]
    assert {"id", "resourceName", "status", "hasParagraph"} <= set(item.keys())


def test_notifications_passes_resource_filter(cn_repo):
    tc, mock = cn_repo
    tc.get("/api/cn/notifications?resource=persons")
    mock.get_notifications.assert_called_with(resource="persons", status=None)


def test_notifications_passes_status_filter(cn_repo):
    tc, mock = cn_repo
    tc.get("/api/cn/notifications?status=Enabled")
    mock.get_notifications.assert_called_with(resource=None, status="Enabled")


# ── Notification detail ───────────────────────────────────────────────────────

def test_notification_detail_200(cn_repo):
    tc, _ = cn_repo
    r = tc.get("/api/cn/notifications/cn-1")
    assert r.status_code == 200
    assert r.get_json()["id"] == "cn-1"


def test_notification_detail_404_when_repo_returns_none(cn_repo):
    tc, mock = cn_repo
    mock.get_notification.return_value = None
    r = tc.get("/api/cn/notifications/missing")
    assert r.status_code == 404


# ── Paragraph ─────────────────────────────────────────────────────────────────

def test_paragraph_200(cn_repo):
    tc, _ = cn_repo
    r = tc.get("/api/cn/notifications/cn-1/paragraph")
    assert r.status_code == 200
    assert {"code", "source"} <= set(r.get_json().keys())


def test_paragraph_404_when_repo_returns_none(cn_repo):
    tc, mock = cn_repo
    mock.get_paragraph.return_value = None
    r = tc.get("/api/cn/notifications/missing/paragraph")
    assert r.status_code == 404


# ── CN history (now sourced from the audit log) ───────────────────────────────

def test_cn_history_returns_audit_entries_for_that_cn(app, cn_repo):
    tc, _ = cn_repo
    with app.app_context():
        AuditEntry.query.delete()
        from app.database import db as _db
        _db.session.commit()
        write_event(Action.VIEW, "cn.notification", "cn-1")
        write_event(Action.VIEW, "cn.notification", "cn-2")
    data = tc.get("/api/cn/notifications/cn-1/history").get_json()
    assert "items" in data
    assert all(item["resource_id"] == "cn-1" for item in data["items"])


# ── Diagnostics ───────────────────────────────────────────────────────────────

def test_diagnostics_shape(cn_repo, mock_ethos):
    tc, _ = cn_repo
    mock_ethos.get_cn_available_resources.return_value = [
        {"resourceName": "persons"}, {"resourceName": "sections"},
    ]
    data = tc.get("/api/cn/diagnostics").get_json()
    assert {"aligned", "subscribedNotPublished", "publishedNotSubscribed",
            "totalSubscribed", "totalPublished"} <= set(data.keys())


def test_diagnostics_passes_subscribed_names_to_repo(cn_repo, mock_ethos):
    tc, mock = cn_repo
    mock_ethos.get_cn_available_resources.return_value = [
        {"resourceName": "persons"}, {"resourceName": "students"},
    ]
    tc.get("/api/cn/diagnostics")
    mock.get_diagnostics.assert_called_once()
    passed = mock.get_diagnostics.call_args[0][0]
    assert sorted(passed) == ["persons", "students"]


# ── Audit log (now reads the local audit table) ───────────────────────────────

def test_audit_log_returns_local_audit_rows(app, client):
    with app.app_context():
        AuditEntry.query.delete()
        from app.database import db as _db
        _db.session.commit()
        write_event(Action.PUBLISH, "ethos.change_notification", "persons")
    data = client.get("/api/cn/audit-log").get_json()
    assert {"items", "totalCount", "page", "pageSize", "totalPages"} <= set(data.keys())
    assert any(i["resource_id"] == "persons" for i in data["items"])


def test_audit_log_pagination(app, client):
    with app.app_context():
        AuditEntry.query.delete()
        from app.database import db as _db
        _db.session.commit()
        for i in range(7):
            write_event(Action.VIEW, "test", f"id-{i}")
    data = client.get("/api/cn/audit-log?page=1&pageSize=3").get_json()
    assert len(data["items"]) == 3
    assert data["totalCount"] == 7
    assert data["totalPages"] == 3


def test_audit_log_filter_by_target_identifier(app, client):
    with app.app_context():
        AuditEntry.query.delete()
        from app.database import db as _db
        _db.session.commit()
        write_event(Action.VIEW, "test", "persons-x")
        write_event(Action.VIEW, "test", "courses-x")
    data = client.get("/api/cn/audit-log?targetIdentifier=persons").get_json()
    assert data["totalCount"] == 1
    assert data["items"][0]["resource_id"] == "persons-x"


# ── Push change notifications ─────────────────────────────────────────────────

@pytest.fixture()
def push_client(app):
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


def test_push_400_missing_resource_name(push_client):
    tc, _ = push_client
    r = tc.post("/api/cn/push", json={"guids": ["abc"]})
    assert r.status_code == 400


def test_push_400_missing_guids(push_client):
    tc, _ = push_client
    r = tc.post("/api/cn/push", json={"resource_name": "persons", "guids": []})
    assert r.status_code == 400


def test_push_200_returns_results(push_client):
    tc, _ = push_client
    data = tc.post("/api/cn/push", json={
        "resource_name": "persons", "operation": "replaced",
        "guids": ["fee12eb6-dae1-456b-a7c4-063458617478"],
    }).get_json()
    assert len(data["results"]) == 1
    assert data["results"][0]["status"] == "success"


def test_push_calls_publish_notification(push_client):
    tc, mock = push_client
    tc.post("/api/cn/push", json={
        "resource_name": "persons", "operation": "created", "guids": ["abc-123"],
    })
    call_args = mock.publish_notification.call_args[0][0]
    assert call_args["resource"]["name"] == "persons"
    assert call_args["operation"] == "created"


def test_push_emits_one_audit_event_per_publish_operation(app, push_client):
    """One audit row per logical publish — never one per fan-out guid."""
    tc, _ = push_client
    with app.app_context():
        AuditEntry.query.delete()
        from app.database import db as _db
        _db.session.commit()
    tc.post("/api/cn/push", json={
        "resource_name": "persons", "operation": "replaced",
        "guids": ["g1", "g2", "g3"],
    })
    with app.app_context():
        rows = AuditEntry.query.filter_by(action=Action.PUBLISH).all()
        assert len(rows) == 1
        assert rows[0].resource_id == "persons"
        assert rows[0].detail["guid_count"] == 3
