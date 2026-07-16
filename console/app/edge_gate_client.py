import logging

import requests

log = logging.getLogger(__name__)


class EdgeGateClient:
    """Polls DoaneEdgeGate's own /health endpoint (see DoaneEdgeGate's
    Program.cs) so the console's Health tab can surface whether the DOB-shift
    prevention proxy sitting in front of the Colleague Web API is actually up
    — the console has no other visibility into it once traffic is repointed
    through the gate instead of straight to Colleague.
    """

    def __init__(self, base_url: str):
        self.base_url = (base_url or "").rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def check_health(self) -> dict:
        if not self.is_configured():
            return {"configured": False, "reachable": False, "status": "unconfigured"}

        try:
            # A health endpoint should never legitimately redirect; without
            # this, a misconfigured EDGE_GATE_URL that redirect-loops ties up
            # the request for up to timeout * max_redirects instead of 5s.
            r = requests.get(f"{self.base_url}/health", timeout=5, allow_redirects=False)
            r.raise_for_status()
            body = r.json()
            if not isinstance(body, dict):
                raise ValueError(f"expected a JSON object, got {type(body).__name__}")
        except Exception as exc:
            log.warning("DoaneEdgeGate health check failed: %s", exc)
            return {"configured": True, "reachable": False, "status": "unreachable", "error": str(exc)}

        return {
            "configured": True,
            "reachable": True,
            "status": body.get("status", "unknown"),
            "service": body.get("service"),
            "version": body.get("version"),
            "uptime_seconds": body.get("uptime_seconds"),
        }
