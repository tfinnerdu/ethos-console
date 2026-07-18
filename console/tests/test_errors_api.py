"""Tests for /api/errors endpoints."""
import json
from datetime import datetime, timedelta, timezone

from app.database import db, EthosErrorLog


def _seed_errors(app, n=5):
    with app.app_context():
        for i in range(n):
            db.session.add(EthosErrorLog(
                source="test",
                endpoint=f"/api/test/{i}",
                http_status=400 + i,
                resource_name="persons",
                error_message=f"error {i}",
            ))
        db.session.commit()


def test_errors_list_empty(client):
    r = client.get("/api/errors/")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data
    assert "total" in data


def test_errors_post_and_retrieve(client, app):
    payload = {
        "source": "test_suite",
        "endpoint": "/api/something",
        "http_status": 503,
        "resource_name": "courses",
        "error_message": "upstream timeout",
    }
    r = client.post("/api/errors/", json=payload)
    assert r.status_code == 201

    r = client.get("/api/errors/?source=test_suite")
    data = r.get_json()
    assert data["total"] >= 1
    assert any(e["source"] == "test_suite" for e in data["items"])


def test_errors_filter_by_status(client, app):
    _seed_errors(app)
    r = client.get("/api/errors/?http_status=429")
    data = r.get_json()
    for item in data["items"]:
        assert item["http_status"] == 429


def test_errors_spikes_shape(client):
    r = client.get("/api/errors/spikes")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)
    if data:
        assert "hour" in data[0]
        assert "count" in data[0]


def test_errors_spikes_buckets_by_hour_and_sorts_descending(client, app):
    # Regression test: /spikes used to run raw strftime() SQL, which is
    # SQLite-only and has no Postgres equivalent — this exercises the actual
    # bucketing/aggregation behavior (not just the response shape), so a
    # dialect regression would be caught here rather than only in production.
    #
    # Asserts deltas, not exact counts: the session-scoped `app`/db fixture
    # is shared across every test in this file, so earlier tests
    # (test_errors_post_and_retrieve, test_errors_filter_by_status's
    # _seed_errors) may have already inserted rows with a "now" timestamp
    # landing in the same hour bucket this test uses.
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    older_hour = now - timedelta(hours=3)
    now_key = now.strftime("%Y-%m-%d %H:00")
    older_key = older_hour.strftime("%Y-%m-%d %H:00")

    def _counts():
        data = client.get("/api/errors/spikes").get_json()
        by_hour = {row["hour"]: row["count"] for row in data}
        return by_hour.get(now_key, 0), by_hour.get(older_key, 0)

    before_now, before_older = _counts()

    with app.app_context():
        for i in range(3):
            db.session.add(EthosErrorLog(
                source="spike_test", endpoint="/x", http_status=500,
                error_message=f"e{i}", timestamp=now + timedelta(minutes=i),
            ))
        db.session.add(EthosErrorLog(
            source="spike_test", endpoint="/x", http_status=500,
            error_message="old", timestamp=older_hour,
        ))
        db.session.commit()

    r = client.get("/api/errors/spikes")
    assert r.status_code == 200
    data = r.get_json()
    by_hour = {row["hour"]: row["count"] for row in data}

    assert by_hour.get(now_key, 0) - before_now == 3
    assert by_hour.get(older_key, 0) - before_older == 1
    # Descending by hour.
    hours = [row["hour"] for row in data]
    assert hours == sorted(hours, reverse=True)


def test_errors_flush(client):
    r = client.post("/api/errors/flush")
    assert r.status_code == 200


def test_errors_flush_emits_one_summary_audit_event(client, app):
    from app.database import AuditEntry
    from unittest.mock import MagicMock
    hm = app.extensions.get("health_monitor")
    hm.error_log = [
        {"source": "s", "endpoint": "/e", "http_status": 500, "error_message": "boom"},
        {"source": "s", "endpoint": "/e", "http_status": 500, "error_message": "boom2"},
    ]
    before = AuditEntry.query.filter_by(action="flush").count()
    client.post("/api/errors/flush")
    with app.app_context():
        after = AuditEntry.query.filter_by(action="flush").count()
    # One summary event for the whole batch, never one per flushed row.
    assert after == before + 1


def test_errors_export_csv(client):
    r = client.get("/api/errors/export")
    assert r.status_code == 200
    assert "text/csv" in r.content_type


def test_errors_list_non_numeric_limit_returns_400_not_500(client):
    r = client.get("/api/errors/?limit=abc")
    assert r.status_code == 400


def test_errors_list_non_numeric_page_returns_400_not_500(client):
    r = client.get("/api/errors/?page=abc")
    assert r.status_code == 400
