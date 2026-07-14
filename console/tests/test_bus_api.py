"""Tests for /api/bus endpoints.

The SSE streaming endpoint (/stream) is excluded — streaming responses
require a real WSGI server to test meaningfully, and all of the interesting
logic is in BusMonitor itself (tested separately in test_bus_monitor.py).
"""


def test_stats_returns_200(client):
    r = client.get("/api/bus/stats")
    assert r.status_code == 200


def test_stats_shape(client):
    data = client.get("/api/bus/stats").get_json()
    assert "running" in data
    assert "queue_depth" in data
    assert "paused" in data
    assert "resource_stats" in data
    assert "buffer_size" in data


# ── Start / Stop ──────────────────────────────────────────────────────────────
# The monitor must default to stopped (no auto-poll against Ethos on boot) and
# only start when explicitly asked to, via this pair of endpoints.

def test_create_app_does_not_auto_start_monitor():
    """Regression guard: Bus Monitor must not auto-poll Ethos on app boot."""
    from unittest.mock import patch
    from app import create_app, get_monitor

    with patch("app.ethos_client.EthosClient.is_configured", return_value=True):
        test_app = create_app("development")
    try:
        assert get_monitor(test_app).running is False
    finally:
        get_monitor(test_app).stop()


def test_stats_running_false_by_default(client):
    assert client.get("/api/bus/stats").get_json()["running"] is False


def test_start_returns_503_when_ethos_not_configured(client):
    r = client.post("/api/bus/start")
    assert r.status_code == 503
    data = r.get_json()
    assert "error" in data
    assert "setup" in data


def test_start_succeeds_when_ethos_configured(app, mock_ethos):
    from app import get_monitor
    client = app.test_client()
    try:
        r = client.post("/api/bus/start")
        assert r.status_code == 200
        assert r.get_json()["running"] is True
        assert client.get("/api/bus/stats").get_json()["running"] is True
    finally:
        get_monitor(app).stop()


def test_stop_returns_running_false(app, mock_ethos):
    from app import get_monitor
    client = app.test_client()
    try:
        client.post("/api/bus/start")
        r = client.post("/api/bus/stop")
        assert r.status_code == 200
        assert r.get_json()["running"] is False
        assert client.get("/api/bus/stats").get_json()["running"] is False
    finally:
        get_monitor(app).stop()


def test_stats_paused_false_initially(client):
    data = client.get("/api/bus/stats").get_json()
    assert data["paused"] is False


def test_pause_returns_paused_true(client):
    r = client.post("/api/bus/pause")
    assert r.status_code == 200
    assert r.get_json() == {"paused": True}


def test_pause_reflected_in_stats(client):
    client.post("/api/bus/pause")
    assert client.get("/api/bus/stats").get_json()["paused"] is True


def test_resume_returns_paused_false(client):
    client.post("/api/bus/pause")
    r = client.post("/api/bus/resume")
    assert r.status_code == 200
    assert r.get_json() == {"paused": False}


def test_resume_reflected_in_stats(client):
    client.post("/api/bus/pause")
    client.post("/api/bus/resume")
    assert client.get("/api/bus/stats").get_json()["paused"] is False


def test_clear_returns_cleared_true(client):
    r = client.post("/api/bus/clear")
    assert r.status_code == 200
    assert r.get_json() == {"cleared": True}


def test_clear_empties_buffer(client):
    client.post("/api/bus/clear")
    assert client.get("/api/bus/stats").get_json()["buffer_size"] == 0


def test_export_returns_plain_text(client):
    r = client.get("/api/bus/export")
    assert r.status_code == 200
    assert "text/plain" in r.content_type


def test_export_attachment_header(client):
    r = client.get("/api/bus/export")
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert "ethos-bus-export.txt" in r.headers.get("Content-Disposition", "")


def test_export_empty_when_no_events(client):
    client.post("/api/bus/clear")
    r = client.get("/api/bus/export")
    assert r.data == b""
