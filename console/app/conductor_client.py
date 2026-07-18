"""Thin HTTP client for Netflix Conductor's workflow API.

Lives behind app.extensions['conductor_client'] so routes call through one
seam — the real client in normal mode, MockConductorClient when
CONSOLE_MOCK_MODE=true.
"""
import requests
from urllib.parse import urlsplit


def _hostname(url: str) -> str:
    """Lowercased hostname of `url`, or "" if it doesn't parse to one.

    Used instead of a substring/.startswith() check specifically because
    those are bypassable via URL-parsing tricks (e.g. userinfo:
    "http://trusted.doane.edu@evil.com/" contains "trusted.doane.edu" as a
    substring but resolves to host evil.com) — urlsplit resolves the same
    trick to the real host correctly.
    """
    return (urlsplit(url).hostname or "").lower()


class ConductorClient:
    def __init__(self, base_url: str = "", api_key: str = "", additional_hosts: str = ""):
        self.base_url = (base_url or "").rstrip("/")
        self._api_key = api_key
        # Extra hostnames (CONDUCTOR_ADDITIONAL_HOSTS, comma-separated) the
        # Replay UI's per-run base_url override is allowed to target, beyond
        # the configured base_url's own host. Anything else is refused
        # outright by trigger_workflow() below — see its docstring for why.
        self._allowed_hosts = {_hostname(base_url)}
        self._allowed_hosts.update(
            h.strip().lower() for h in additional_hosts.split(",") if h.strip()
        )

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def trigger_workflow(self, name: str, payload: dict, base_url: str | None = None) -> str:
        """POST {base}/api/workflow/{name} with the given payload.

        Returns the workflow execution id Conductor responds with.
        `base_url` overrides the configured one (the Replay UI lets the
        operator point at a different Conductor per run) — but only to a
        host in self._allowed_hosts. This isn't just an SSRF guard: the
        real Conductor API key is attached to every request below, so an
        unrestricted override would hand that key to whatever host a caller
        supplies. Raises ValueError (a validation failure, not a Conductor-
        side error) for an unlisted host, before any request is sent.
        """
        url = (base_url or self.base_url).rstrip("/")
        if not url:
            raise RuntimeError("Conductor base URL is not configured")
        host = _hostname(url)
        if host not in self._allowed_hosts:
            raise ValueError(
                f"conductor_url host {host!r} is not allow-listed — add it to "
                "CONDUCTOR_ADDITIONAL_HOSTS to permit this override"
            )
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
