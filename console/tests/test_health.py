"""Tests for /api/health endpoints."""


def test_liveness_always_200(client):
    r = client.get("/api/health/live")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"


def test_health_check_shape(client):
    r = client.get("/api/health/")
    assert r.status_code == 200
    data = r.get_json()
    assert "token" in data
    assert "queue_depth" in data
    assert "latency" in data
    assert "recent_errors" in data
    assert "resource_health" in data
    assert "ethos_configured" in data


def test_health_latency_keys(client):
    data = client.get("/api/health/").get_json()
    lat = data["latency"]
    assert set(lat.keys()) >= {"p50", "p95", "p99", "max", "sample_count"}
