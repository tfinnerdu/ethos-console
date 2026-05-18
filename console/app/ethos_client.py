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
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "Accept": accept,
            "Content-Type": "application/json",
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
        r = requests.get(
            f"{self.base_url}/api/available-resources",
            headers=self.get_headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json() or []

    def get_cn_available_resources(self) -> list:
        r = requests.get(
            f"{self.base_url}/api/change-notifications/available-resources",
            headers=self.get_headers(),
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
