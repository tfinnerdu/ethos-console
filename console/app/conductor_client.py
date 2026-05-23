"""Thin HTTP client for Netflix Conductor's workflow API.

Lives behind app.extensions['conductor_client'] so routes call through one
seam — the real client in normal mode, MockConductorClient when
CONSOLE_MOCK_MODE=true.
"""
import requests


class ConductorClient:
    def __init__(self, base_url: str = "", api_key: str = ""):
        self.base_url = (base_url or "").rstrip("/")
        self._api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def trigger_workflow(self, name: str, payload: dict, base_url: str | None = None) -> str:
        """POST {base}/api/workflow/{name} with the given payload.

        Returns the workflow execution id Conductor responds with.
        `base_url` overrides the configured one (the Replay UI lets the
        operator point at a different Conductor per run).
        """
        url = (base_url or self.base_url).rstrip("/")
        if not url:
            raise RuntimeError("Conductor base URL is not configured")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-Authorization"] = self._api_key
        r = requests.post(
            f"{url}/api/workflow/{name}",
            headers=headers,
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.text.strip().strip('"')

    @staticmethod
    def workflow_url(base_url: str, workflow_id: str) -> str:
        return f"{base_url.rstrip('/')}/api/workflow/{workflow_id}"
