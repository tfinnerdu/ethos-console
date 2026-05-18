import threading
import time
import logging
from collections import deque, defaultdict
from datetime import datetime, timezone

log = logging.getLogger(__name__)


class BusMonitor:
    def __init__(self, ethos_client):
        self.client = ethos_client
        self.event_buffer: deque = deque(maxlen=500)
        self.resource_stats: dict = defaultdict(
            lambda: {"count": 0, "last_seen": None, "first_seen": None}
        )
        self.queue_depth: int = 0
        self.last_poll: float | None = None
        self.running = False
        self.paused = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._poll_interval: int = 2
        self._app = None

    def start(self, poll_interval: int = 2, app=None):
        if self.running:
            return
        self._poll_interval = poll_interval
        self._app = app
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="bus-monitor")
        self._thread.start()
        log.info("BusMonitor started (poll interval: %ds)", poll_interval)

    def stop(self):
        self.running = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def clear(self):
        with self._lock:
            self.event_buffer.clear()

    def _poll_loop(self):
        while self.running:
            if not self.paused and self.client.is_configured():
                try:
                    start = time.monotonic()
                    messages = self.client.consume_messages(limit=20)
                    elapsed_ms = (time.monotonic() - start) * 1000

                    for msg in messages:
                        self._process_message(msg)

                    try:
                        self.queue_depth = self.client.get_queue_depth()
                    except Exception:
                        pass

                    self.last_poll = time.time()
                except Exception as exc:
                    with self._lock:
                        self.event_buffer.append({
                            "type": "error",
                            "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                            "message": str(exc),
                        })
                    log.warning("BusMonitor poll error: %s", exc)
                    if self._app:
                        try:
                            with self._app.app_context():
                                from app.database import db, EthosErrorLog
                                entry = EthosErrorLog(source="bus_monitor", endpoint="/consume", error_message=str(exc))
                                db.session.add(entry)
                                db.session.commit()
                        except Exception:
                            pass

            time.sleep(self._poll_interval)

    def _process_message(self, msg: dict):
        resource = msg.get("resource", {}).get("name", "unknown")
        operation = msg.get("resource", {}).get("operation", "unknown")
        guid = msg.get("resource", {}).get("id", "")
        content_type = msg.get("contentType", "")
        msg_id = msg.get("id", 0)
        now = time.time()
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

        event = {
            "type": "event",
            "timestamp": ts,
            "resource": resource,
            "operation": operation,
            "guid": guid,
            "content_type": content_type,
            "id": msg_id,
        }

        with self._lock:
            self.event_buffer.append(event)
            stats = self.resource_stats[resource]
            stats["count"] += 1
            stats["last_seen"] = now
            if stats["first_seen"] is None:
                stats["first_seen"] = now

    def get_events(self, since_index: int = 0) -> tuple[list, int]:
        with self._lock:
            buf = list(self.event_buffer)
        return buf[since_index:], len(buf)

    def get_resource_stats(self) -> list:
        now = time.time()
        with self._lock:
            stats = dict(self.resource_stats)
        result = []
        for resource, s in stats.items():
            last_seen = s["last_seen"]
            first_seen = s["first_seen"]
            elapsed = (now - last_seen) if last_seen else None
            duration_hours = ((now - first_seen) / 3600) if first_seen else 1
            rate = round(s["count"] / max(duration_hours, 0.016667)) if s["count"] > 0 else 0
            result.append({
                "resource": resource,
                "count": s["count"],
                "last_seen_seconds_ago": round(elapsed) if elapsed is not None else None,
                "events_per_hour": rate,
                "status": _resource_status(elapsed),
            })
        return sorted(result, key=lambda x: x["count"], reverse=True)

    def get_silent_resources(self, threshold_minutes: int = 30) -> list:
        now = time.time()
        with self._lock:
            stats = dict(self.resource_stats)
        return [
            r
            for r, s in stats.items()
            if s["last_seen"] and (now - s["last_seen"]) > threshold_minutes * 60
        ]

    def export_events(self, limit: int = 100) -> list:
        with self._lock:
            buf = list(self.event_buffer)
        return buf[-limit:]


def _resource_status(elapsed_seconds: float | None) -> str:
    if elapsed_seconds is None:
        return "unknown"
    if elapsed_seconds < 1800:
        return "active"
    return "silent"
