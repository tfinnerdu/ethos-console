import base64

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context


# OpenSSL 3.x option byte to allow handshakes with servers that don't
# advertise the RFC 5746 secure-renegotiation extension. On-prem Colleague
# Web API installations on older IIS / Schannel stacks fall in that bucket
# and refuse the TLS handshake with `[SSL: UNEXPECTED_EOF_WHILE_READING]`
# under modern Python without this flag.
_OP_LEGACY_SERVER_CONNECT = 0x4


class _LegacyTlsAdapter(HTTPAdapter):
    """HTTPAdapter scoped to ColleagueApiClient that allows unsafe legacy
    renegotiation. Does not change global TLS defaults for Ethos / Conductor
    calls.
    """

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.options |= _OP_LEGACY_SERVER_CONNECT
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class ColleagueApiClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._session = requests.Session()
        self._session.mount("https://", _LegacyTlsAdapter())

    def is_configured(self) -> bool:
        return bool(self.base_url and self._username)

    def _headers(self) -> dict:
        creds = base64.b64encode(
            f"{self._username}:{self._password}".encode()
        ).decode()
        # Content-Type is added by `requests` when `json=...` is supplied on
        # POST; intentionally omitted on the default so body-less GETs don't
        # send a Content-Type that some IIS-hosted routes reject.
        return {
            "Authorization": f"Basic {creds}",
            "Accept": "application/json",
        }

    def get_about(self) -> dict:
        r = self._session.get(
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
        r = self._session.get(
            f"{self.base_url}/api/event-configurations",
            headers=self._headers(),
            params=params,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    def call_transaction(self, transaction_id: str, payload: dict) -> dict:
        r = self._session.post(
            f"{self.base_url}/api/transactions/{transaction_id}",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def get_metadata_manifest(self, api_domain: str, api_type: str) -> dict:
        r = self._session.get(
            f"{self.base_url}/api/metadata/manifest/{api_domain}/{api_type}",
            headers=self._headers(),
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
