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
    assert "queue_depth" in data
    assert "paused" in data
    assert "resource_stats" in data
    assert "buffer_size" in data


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
