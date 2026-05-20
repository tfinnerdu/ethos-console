import base64
import requests


class ColleagueApiClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self._username = username
        self._password = password

    def is_configured(self) -> bool:
        return bool(self.base_url and self._username)

    def _headers(self) -> dict:
        creds = base64.b64encode(
            f"{self._username}:{self._password}".encode()
        ).decode()
        return {
            "Authorization": f"Basic {creds}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_about(self) -> dict:
        r = requests.get(
            f"{self.base_url}/api/about",
            headers=self._headers(),
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def get_event_configurations(self, resource_name: str | None = None) -> list:
        params = {}
        if resource_name:
            params["resourceName"] = resource_name
        r = requests.get(
            f"{self.base_url}/api/event-configurations",
            headers=self._headers(),
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def call_transaction(self, transaction_id: str, payload: dict) -> dict:
        r = requests.post(
            f"{self.base_url}/api/transactions/{transaction_id}",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def get_metadata_manifest(self, api_domain: str, api_type: str) -> dict:
        r = requests.get(
            f"{self.base_url}/api/metadata/manifest/{api_domain}/{api_type}",
            headers=self._headers(),
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
