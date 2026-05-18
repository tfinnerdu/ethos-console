import time
import logging
from collections import deque, defaultdict
from datetime import datetime, timezone

log = logging.getLogger(__name__)


class EthosHealthMonitor:
    def __init__(self, ethos_client):
        self.client = ethos_client
        self.api_latencies: deque = deque(maxlen=100)
        self.error_log: deque = deque(maxlen=200)
        self.resource_last_seen: dict = defaultdict(lambda: None)
        self.resource_hourly_count: dict = defaultdict(int)
        self._start_time = time.time()

    def record_api_call(self, endpoint: str, duration_ms: float, status_code: int):
        self.api_latencies.append(duration_ms)
        if status_code >= 400:
            self.error_log.append({
                "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "endpoint": endpoint,
                "status": status_code,
                "occurrence": 1,
            })
            log.debug("Ethos API error %d on %s (%.0fms)", status_code, endpoint, duration_ms)

    def record_event(self, resource: str):
        self.resource_last_seen[resource] = time.time()
        self.resource_hourly_count[resource] += 1

    def record_error(self, source: str, message: str):
        self.error_log.append({
            "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "endpoint": source,
            "status": 0,
            "message": message,
        })

    def get_latency_percentiles(self) -> dict:
        if not self.api_latencies:
            return {"p50": None, "p95": None, "p99": None, "max": None, "sample_count": 0}
        sorted_l = sorted(self.api_latencies)
        n = len(sorted_l)

        def pct(p: float) -> float:
            return round(sorted_l[int((n - 1) * p)])

        return {
            "p50": pct(0.50),
            "p95": pct(0.95),
            "p99": pct(0.99),
            "max": round(sorted_l[-1]),
            "sample_count": n,
        }

    def get_token_status(self) -> dict:
        return self.client.token_status

    def get_resource_health(self) -> list:
        now = time.time()
        elapsed_since_start_hours = (now - self._start_time) / 3600
        result = []
        all_resources = set(list(self.resource_last_seen.keys()) + list(self.resource_hourly_count.keys()))
        for resource in all_resources:
            last = self.resource_last_seen.get(resource)
            count = self.resource_hourly_count.get(resource, 0)
            elapsed = (now - last) if last else None
            rate = round(count / max(elapsed_since_start_hours, 0.016667)) if count else 0
            result.append({
                "resource": resource,
                "hourly_rate": rate,
                "last_seen_seconds_ago": round(elapsed) if elapsed is not None else None,
                "status": "green" if elapsed and elapsed < 1800 else "amber",
            })
        return sorted(result, key=lambda x: x["hourly_rate"], reverse=True)

    def check_health(self) -> dict:
        queue_depth = 0
        queue_error = None
        if self.client.is_configured():
            try:
                queue_depth = self.client.get_queue_depth()
            except Exception as exc:
                queue_error = str(exc)

        queue_status = (
            "red" if queue_error else
            "red" if queue_depth >= 500 else
            "amber" if queue_depth >= 100 else
            "green"
        )

        recent_errors = list(self.error_log)[-10:]
        error_count_1h = len([e for e in self.error_log])

        return {
            "token": self.get_token_status(),
            "queue_depth": queue_depth,
            "queue_status": queue_status,
            "queue_error": queue_error,
            "latency": self.get_latency_percentiles(),
            "recent_errors": recent_errors,
            "error_count_1h": error_count_1h,
            "error_status": "red" if error_count_1h > 10 else "amber" if error_count_1h > 0 else "green",
            "resource_health": self.get_resource_health(),
            "ethos_configured": self.client.is_configured(),
        }
