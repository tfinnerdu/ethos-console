"""Unit tests for BusMonitor pure-logic methods.

No threading. No live Ethos. Tests the in-memory data structures
and helper functions in isolation.
"""
import time
from unittest.mock import MagicMock
from app.bus_monitor import BusMonitor, _resource_status


def _monitor():
    client = MagicMock()
    client.is_configured.return_value = True
    return BusMonitor(client)


def _msg(resource="persons", operation="updated", guid="abc-123", msg_id=1):
    return {
        "id": msg_id,
        "resource": {"name": resource, "operation": operation, "id": guid},
        "contentType": "application/vnd.hedtech.integration.v16+json",
    }


# ── pause / resume / clear ────────────────────────────────────────────────────

def test_initially_not_paused():
    m = _monitor()
    assert m.paused is False


def test_pause_sets_flag():
    m = _monitor()
    m.pause()
    assert m.paused is True


def test_resume_clears_flag():
    m = _monitor()
    m.pause()
    m.resume()
    assert m.paused is False


def test_clear_empties_buffer():
    m = _monitor()
    m._process_message(_msg())
    m._process_message(_msg(msg_id=2))
    m.clear()
    events, total = m.get_events()
    assert total == 0
    assert events == []


# ── _process_message ──────────────────────────────────────────────────────────

def test_process_message_adds_to_buffer():
    m = _monitor()
    m._process_message(_msg())
    _, total = m.get_events()
    assert total == 1


def test_process_message_event_shape():
    m = _monitor()
    m._process_message(_msg(resource="courses", operation="created", guid="xyz"))
    events, _ = m.get_events()
    e = events[0]
    assert e["type"] == "event"
    assert e["resource"] == "courses"
    assert e["operation"] == "created"
    assert e["guid"] == "xyz"
    assert "timestamp" in e
    assert "id" in e


def test_process_message_increments_resource_stats():
    m = _monitor()
    m._process_message(_msg(resource="persons", msg_id=1))
    m._process_message(_msg(resource="persons", msg_id=2))
    assert m.resource_stats["persons"]["count"] == 2


def test_process_message_sets_last_seen():
    m = _monitor()
    before = time.time()
    m._process_message(_msg())
    assert m.resource_stats["persons"]["last_seen"] >= before


def test_process_message_sets_first_seen_once():
    m = _monitor()
    m._process_message(_msg(msg_id=1))
    first = m.resource_stats["persons"]["first_seen"]
    m._process_message(_msg(msg_id=2))
    assert m.resource_stats["persons"]["first_seen"] == first


def test_process_unknown_resource_defaults_to_unknown():
    m = _monitor()
    m._process_message({"id": 1, "resource": {}, "contentType": ""})
    events, _ = m.get_events()
    assert events[0]["resource"] == "unknown"


# ── get_events ────────────────────────────────────────────────────────────────

def test_get_events_since_index_slices_correctly():
    m = _monitor()
    for i in range(5):
        m._process_message(_msg(msg_id=i))
    events, total = m.get_events(since_index=3)
    assert total == 5
    assert len(events) == 2


def test_get_events_since_index_zero_returns_all():
    m = _monitor()
    for i in range(3):
        m._process_message(_msg(msg_id=i))
    events, total = m.get_events(since_index=0)
    assert len(events) == total == 3


def test_get_events_empty_buffer():
    m = _monitor()
    events, total = m.get_events()
    assert events == []
    assert total == 0


# ── get_resource_stats ────────────────────────────────────────────────────────

def test_get_resource_stats_empty():
    m = _monitor()
    assert m.get_resource_stats() == []


def test_get_resource_stats_sorted_by_count_desc():
    m = _monitor()
    for _ in range(5):
        m._process_message(_msg(resource="persons"))
    for _ in range(2):
        m._process_message(_msg(resource="courses"))
    stats = m.get_resource_stats()
    assert stats[0]["resource"] == "persons"
    assert stats[0]["count"] == 5
    assert stats[1]["resource"] == "courses"


def test_get_resource_stats_shape():
    m = _monitor()
    m._process_message(_msg())
    stat = m.get_resource_stats()[0]
    assert set(stat.keys()) == {"resource", "count", "last_seen_seconds_ago",
                                "events_per_hour", "status"}


def test_get_resource_stats_status_active_for_recent():
    m = _monitor()
    m._process_message(_msg())
    stat = m.get_resource_stats()[0]
    assert stat["status"] == "active"


# ── get_silent_resources ──────────────────────────────────────────────────────

def test_get_silent_resources_empty_when_all_recent():
    m = _monitor()
    m._process_message(_msg())
    silent = m.get_silent_resources(threshold_minutes=30)
    assert "persons" not in silent


def test_get_silent_resources_catches_old_events(monkeypatch):
    m = _monitor()
    m._process_message(_msg(resource="stale"))
    # Wind the clock back 2 hours on the last_seen
    m.resource_stats["stale"]["last_seen"] -= 7200
    silent = m.get_silent_resources(threshold_minutes=30)
    assert "stale" in silent


# ── export_events ─────────────────────────────────────────────────────────────

def test_export_events_returns_last_n():
    m = _monitor()
    for i in range(10):
        m._process_message(_msg(msg_id=i))
    exported = m.export_events(limit=3)
    assert len(exported) == 3
    assert exported[-1]["id"] == 9  # most recent


def test_export_events_all_when_limit_exceeds_buffer():
    m = _monitor()
    for i in range(5):
        m._process_message(_msg(msg_id=i))
    exported = m.export_events(limit=100)
    assert len(exported) == 5


# ── _resource_status helper ───────────────────────────────────────────────────

def test_resource_status_none_is_unknown():
    assert _resource_status(None) == "unknown"


def test_resource_status_recent_is_active():
    assert _resource_status(60) == "active"     # 1 minute ago


def test_resource_status_at_boundary():
    assert _resource_status(1799) == "active"   # 29m59s — still active
    assert _resource_status(1800) == "silent"   # exactly 30 min


def test_resource_status_old_is_silent():
    assert _resource_status(7200) == "silent"   # 2 hours ago
