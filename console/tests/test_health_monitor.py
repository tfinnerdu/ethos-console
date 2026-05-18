"""Unit tests for EthosHealthMonitor — pure in-memory logic, no Ethos calls."""
import time
from unittest.mock import MagicMock
from app.health_monitor import EthosHealthMonitor


def _monitor():
    client = MagicMock()
    client.token_status = {"valid": True, "expires_in_minutes": 45}
    client.is_configured.return_value = True
    client.get_queue_depth.return_value = 0
    return EthosHealthMonitor(client)


# ── record_api_call ───────────────────────────────────────────────────────────

def test_record_api_call_adds_to_latencies():
    m = _monitor()
    m.record_api_call("/api/persons", 120.5, 200)
    assert len(m.api_latencies) == 1


def test_record_api_call_4xx_adds_to_error_log():
    m = _monitor()
    m.record_api_call("/api/persons", 50.0, 404)
    assert len(m.error_log) == 1
    assert m.error_log[-1]["status"] == 404


def test_record_api_call_5xx_adds_to_error_log():
    m = _monitor()
    m.record_api_call("/api/persons", 50.0, 500)
    assert len(m.error_log) == 1


def test_record_api_call_2xx_does_not_log_error():
    m = _monitor()
    m.record_api_call("/api/persons", 50.0, 200)
    assert len(m.error_log) == 0


def test_record_api_call_3xx_does_not_log_error():
    m = _monitor()
    m.record_api_call("/api/redirect", 30.0, 302)
    assert len(m.error_log) == 0


# ── record_event ──────────────────────────────────────────────────────────────

def test_record_event_updates_last_seen():
    m = _monitor()
    before = time.time()
    m.record_event("persons")
    assert m.resource_last_seen["persons"] >= before


def test_record_event_increments_count():
    m = _monitor()
    m.record_event("persons")
    m.record_event("persons")
    assert m.resource_hourly_count["persons"] == 2


def test_record_event_tracks_different_resources_independently():
    m = _monitor()
    m.record_event("persons")
    m.record_event("persons")
    m.record_event("courses")
    assert m.resource_hourly_count["persons"] == 2
    assert m.resource_hourly_count["courses"] == 1


# ── record_error ──────────────────────────────────────────────────────────────

def test_record_error_appends_to_log():
    m = _monitor()
    m.record_error("bus_monitor", "Connection refused")
    assert len(m.error_log) == 1
    entry = m.error_log[-1]
    assert entry["endpoint"] == "bus_monitor"
    assert entry["message"] == "Connection refused"
    assert entry["status"] == 0


# ── get_latency_percentiles ───────────────────────────────────────────────────

def test_latency_percentiles_empty():
    m = _monitor()
    p = m.get_latency_percentiles()
    assert p == {"p50": None, "p95": None, "p99": None, "max": None, "sample_count": 0}


def test_latency_percentiles_single_sample():
    m = _monitor()
    m.api_latencies.append(200.0)
    p = m.get_latency_percentiles()
    assert p["p50"] == 200
    assert p["max"] == 200
    assert p["sample_count"] == 1


def test_latency_percentiles_correct_values():
    m = _monitor()
    # 100 samples: 1..100 ms
    for i in range(1, 101):
        m.api_latencies.append(float(i))
    p = m.get_latency_percentiles()
    assert p["p50"] == 50
    assert p["p95"] == 95
    assert p["p99"] == 99
    assert p["max"] == 100
    assert p["sample_count"] == 100


# ── get_token_status ──────────────────────────────────────────────────────────

def test_get_token_status_delegates_to_client():
    m = _monitor()
    m.client.token_status = {"valid": True, "expires_in_minutes": 30}
    assert m.get_token_status() == {"valid": True, "expires_in_minutes": 30}


# ── get_resource_health ───────────────────────────────────────────────────────

def test_get_resource_health_empty_initially():
    m = _monitor()
    assert m.get_resource_health() == []


def test_get_resource_health_recent_event_is_green():
    m = _monitor()
    m.record_event("persons")
    health = m.get_resource_health()
    persons = next(r for r in health if r["resource"] == "persons")
    assert persons["status"] == "green"


def test_get_resource_health_old_event_is_amber():
    m = _monitor()
    m.record_event("stale")
    # Simulate 40 minutes ago
    m.resource_last_seen["stale"] -= 2400
    health = m.get_resource_health()
    stale = next(r for r in health if r["resource"] == "stale")
    assert stale["status"] == "amber"


def test_get_resource_health_sorted_by_rate_desc():
    m = _monitor()
    for _ in range(10):
        m.record_event("persons")
    for _ in range(2):
        m.record_event("courses")
    health = m.get_resource_health()
    assert health[0]["resource"] == "persons"


def test_get_resource_health_shape():
    m = _monitor()
    m.record_event("persons")
    entry = m.get_resource_health()[0]
    assert set(entry.keys()) == {"resource", "hourly_rate", "last_seen_seconds_ago", "status"}


# ── check_health queue thresholds ─────────────────────────────────────────────

def test_check_health_queue_green_below_100():
    m = _monitor()
    m.client.get_queue_depth.return_value = 50
    result = m.check_health()
    assert result["queue_status"] == "green"


def test_check_health_queue_amber_at_100():
    m = _monitor()
    m.client.get_queue_depth.return_value = 100
    result = m.check_health()
    assert result["queue_status"] == "amber"


def test_check_health_queue_red_at_500():
    m = _monitor()
    m.client.get_queue_depth.return_value = 500
    result = m.check_health()
    assert result["queue_status"] == "red"


def test_check_health_queue_red_on_error():
    m = _monitor()
    m.client.get_queue_depth.side_effect = Exception("timeout")
    result = m.check_health()
    assert result["queue_status"] == "red"
    assert result["queue_error"] is not None


# ── check_health error thresholds ─────────────────────────────────────────────

def test_check_health_error_status_green_when_no_errors():
    m = _monitor()
    result = m.check_health()
    assert result["error_status"] == "green"


def test_check_health_error_status_amber_with_few_errors():
    m = _monitor()
    for i in range(5):
        m.record_api_call(f"/api/{i}", 50.0, 500)
    result = m.check_health()
    assert result["error_status"] == "amber"


def test_check_health_error_status_red_above_10():
    m = _monitor()
    for i in range(11):
        m.record_api_call(f"/api/{i}", 50.0, 500)
    result = m.check_health()
    assert result["error_status"] == "red"


def test_check_health_ethos_configured_true():
    m = _monitor()
    m.client.is_configured.return_value = True
    assert m.check_health()["ethos_configured"] is True


def test_check_health_ethos_configured_false():
    m = _monitor()
    m.client.is_configured.return_value = False
    assert m.check_health()["ethos_configured"] is False
