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
        # Monotonic count of every event ever appended, independent of the
        # buffer's maxlen. get_events()/bus_stream() index against this, not
        # len(event_buffer) — once total events exceed 500, the deque evicts
        # from the left while len() stays pinned at 500, which previously
        # pinned the SSE stream's cursor at 500 forever and silently froze it.
        self._total_events: int = 0
        self.resource_stats: dict = defaultdict(
            lambda: {"count": 0, "last_seen": None, "first_seen": None}
        )
        self.queue_depth: int = 0
        self.last_poll: float | None = None
        self.running = False
        self.paused = False
        self._thread: threading.Thread | None = None
        # RLock, not Lock: _check_silence_alerts takes this lock and then
        # calls get_silent_resources(), which takes it again on the same
        # thread — a plain Lock would deadlock there.
        self._lock = threading.RLock()
        self._poll_interval: int = 2
        self._app = None
        self._webhook_url: str = ""
        self._silence_threshold_minutes: int = 30
        self._error_threshold: int = 10
        self._silence_alerted: set = set()
        self._error_timestamps: list = []
        self._error_spike_alerted: bool = False

    def start(self, poll_interval: int = 2, app=None):
        with self._lock:
            if self.running:
                return
            self.running = True
        self._poll_interval = poll_interval
        self._app = app
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
            self._total_events = 0

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
                        self._total_events += 1
                        self._error_timestamps.append(time.time())
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

                if self._webhook_url:
                    self._check_silence_alerts()
                    self._check_error_spike_alerts()

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
            self._total_events += 1
            stats = self.resource_stats[resource]
            stats["count"] += 1
            stats["last_seen"] = now
            if stats["first_seen"] is None:
                stats["first_seen"] = now

    def get_events(self, since_index: int = 0) -> tuple[list, int]:
        """Return (new_events, total) where `total` is a monotonic event
        count, not len(event_buffer) — the buffer is capped at maxlen=500 and
        evicts from the left, so len() alone can't be compared against a
        caller's previous `total` once more than 500 events have occurred.
        If since_index falls before the oldest event still buffered (the
        caller fell behind the eviction window), return everything currently
        available rather than an empty/negative slice.
        """
        with self._lock:
            buf = list(self.event_buffer)
            total = self._total_events
        buffer_start = total - len(buf)
        offset = max(since_index - buffer_start, 0)
        return buf[offset:], total

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

    def _check_silence_alerts(self):
        # Compute-and-reassign _silence_alerted atomically under the lock
        # (get_silent_resources() re-enters the same RLock on this thread) so
        # a concurrent reset() (e.g. from an environment switch) can't
        # interleave between the read and the reassignment and silently
        # resurrect an alert state reset() just cleared.
        from app.alerts import send_alert
        with self._lock:
            now_silent = set(self.get_silent_resources(self._silence_threshold_minutes))
            newly_silent = now_silent - self._silence_alerted
            self._silence_alerted = now_silent
        for resource in newly_silent:
            send_alert(
                self._webhook_url,
                f"Bus Silence: {resource}",
                f"No events received for **{resource}** in the last "
                f"{self._silence_threshold_minutes} minutes.",
            )

    def _check_error_spike_alerts(self):
        from app.alerts import send_alert
        cutoff = time.time() - 3600
        with self._lock:
            self._error_timestamps = [t for t in self._error_timestamps if t > cutoff]
            count = len(self._error_timestamps)
            should_alert = count >= self._error_threshold and not self._error_spike_alerted
            if should_alert:
                self._error_spike_alerted = True
            elif count < self._error_threshold:
                self._error_spike_alerted = False
        if should_alert:
            send_alert(
                self._webhook_url,
                "Ethos Error Spike",
                f"{count} bus poll errors in the last hour. Check the Errors tab for details.",
            )

    def reset(self):
        with self._lock:
            self.event_buffer.clear()
            self._total_events = 0
            self.resource_stats.clear()
            self.queue_depth = 0
            self.last_poll = None
            self._silence_alerted.clear()
            self._error_timestamps.clear()
            self._error_spike_alerted = False

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
