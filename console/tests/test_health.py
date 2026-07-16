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


def test_edge_gate_health_unconfigured_by_default(client):
    # The test app fixture has no EDGE_GATE_URL set.
    r = client.get("/api/health/edge-gate")
    assert r.status_code == 200
    data = r.get_json()
    assert data["configured"] is False
    assert data["reachable"] is False


def test_edge_gate_health_does_not_affect_main_health_payload(client):
    # The gate check is its own endpoint precisely so it can never hold up or
    # break the token/queue/latency/error tiles.
    r = client.get("/api/health/")
    assert r.status_code == 200
    assert "edge_gate" not in r.get_json()


def test_refresh_caches_response_shape(client):
    r = client.post("/api/health/caches/refresh")
    assert r.status_code == 200
    data = r.get_json()
    assert data["refreshed"] is True
    assert set(data["cleared"]) == {"graphql_schema", "available_resources", "cn_resources"}


def test_refresh_caches_actually_clears_module_state(client):
    import app.routes.graphql_routes as gr
    import app.routes.resources as rr

    gr._schema_cache = {"stale": "schema"}
    gr._schema_cache_time = 123.0
    rr._resource_cache = [{"stale": "resource"}]
    rr._resource_source = "stale-source"
    rr._cn_resource_cache = [{"stale": "cn"}]

    r = client.post("/api/health/caches/refresh")
    assert r.status_code == 200

    assert gr._schema_cache is None
    assert gr._schema_cache_time == 0.0
    assert rr._resource_cache == []
    assert rr._resource_source == ""
    assert rr._cn_resource_cache == []
