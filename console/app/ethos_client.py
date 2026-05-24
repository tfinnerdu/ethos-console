import requests
import time
from datetime import datetime, timedelta, timezone


class EthosClient:
    def __init__(self, api_key: str, base_url: str = "https://integrate.elluciancloud.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._token: str | None = None
        self._token_expiry: datetime | None = None

    def get_token(self) -> str:
        now = datetime.now(timezone.utc)
        if self._token and self._token_expiry and now < self._token_expiry:
            return self._token

        r = requests.post(
            f"{self.base_url}/auth",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=15,
        )
        r.raise_for_status()
        self._token = r.text.strip().strip('"')
        self._token_expiry = now + timedelta(minutes=55)
        return self._token

    def get_headers(self, accept: str = "application/json") -> dict:
        # No Content-Type on the default — methods that POST a body either pass
        # `json=...` (requests auto-sets application/json) or override the
        # header explicitly. Sending Content-Type on a body-less GET trips
        # routing on some Ellucian gateways and was causing 404s on
        # /api/available-resources for tenants that worked over curl.
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Accept": accept,
        }

    def get_resource(self, resource: str, params: dict | None = None, version: str | None = None) -> list | dict:
        accept = (
            f"application/vnd.hedtech.integration.v{version}+json"
            if version
            else "application/json"
        )
        r = requests.get(
            f"{self.base_url}/api/{resource}",
            headers=self.get_headers(accept),
            params=params or {},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        body: dict = {"query": query}
        if variables:
            body["variables"] = variables
        r = requests.post(
            f"{self.base_url}/graphql",
            headers=self.get_headers(),
            json=body,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def consume_messages(self, limit: int = 20, last_processed_id: int | None = None) -> list:
        params: dict = {"limit": limit}
        if last_processed_id is not None:
            params["lastProcessedID"] = last_processed_id
        r = requests.get(
            f"{self.base_url}/consume",
            headers=self.get_headers(),
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        return r.json() or []

    def get_queue_depth(self) -> int:
        r = requests.get(
            f"{self.base_url}/consume/count",
            headers=self.get_headers(),
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return int(data) if isinstance(data, (int, str)) else int(data.get("count", 0))

    def get_available_resources(self) -> list:
        # Ellucian's Integration gateway returns 404 on many tenants when this
        # endpoint receives plain application/json — it expects the versioned
        # available-resources media type. Send both so the gateway can pick
        # whichever it supports for this tenant.
        r = requests.get(
            f"{self.base_url}/api/available-resources",
            headers=self.get_headers(
                "application/vnd.hedtech.integration.available-resources.v1+json, application/json"
            ),
            timeout=30,
        )
        r.raise_for_status()
        return r.json() or []

    def get_resource_by_id(self, resource: str, guid: str) -> tuple[dict, str]:
        r = requests.get(
            f"{self.base_url}/api/{resource}/{guid}",
            headers=self.get_headers(),
            timeout=30,
        )
        r.raise_for_status()
        version = r.headers.get("x-media-type") or "application/json"
        return r.json(), version

    def publish_notification(self, notification: dict) -> dict:
        headers = self.get_headers()
        headers["Content-Type"] = "application/vnd.hedtech.change-notifications.v2+json"
        r = requests.post(
            f"{self.base_url}/publish",
            headers=headers,
            json=notification,
            timeout=30,
        )
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {}

    def get_cn_available_resources(self) -> list:
        # Same dual-Accept as /api/available-resources — most tenants need the
        # versioned media type; some accept plain JSON.
        r = requests.get(
            f"{self.base_url}/api/change-notifications/available-resources",
            headers=self.get_headers(
                "application/vnd.hedtech.integration.available-resources.v1+json, application/json"
            ),
            timeout=30,
        )
        r.raise_for_status()
        return r.json() or []

    @property
    def token_status(self) -> dict:
        now = datetime.now(timezone.utc)
        if not self._token or not self._token_expiry:
            return {"valid": False, "expires_in_minutes": 0}
        remaining = (self._token_expiry - now).total_seconds() / 60
        return {"valid": remaining > 0, "expires_in_minutes": round(max(remaining, 0))}

    def is_configured(self) -> bool:
        return bool(self.api_key)
