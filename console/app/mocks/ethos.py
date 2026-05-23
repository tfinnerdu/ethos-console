"""Mock EthosClient. Active only when CONSOLE_MOCK_MODE=true.

Returns shaped fixtures for every method the real EthosClient exposes. No
network calls. Hard separation from real mode — there is no per-method
"try real, fall back to mock" path anywhere.
"""
import itertools
import time

from app.ethos_client import EthosClient
from . import fixtures


class MockEthosClient(EthosClient):
    def __init__(self):
        super().__init__(api_key="MOCK", base_url="https://mock.ethos.local")
        self._token = "mock-token-not-real"
        self._stream = itertools.cycle(fixtures.cn_stream_template_pool())
        # Start id high enough that real-id collisions can't happen accidentally.
        self._next_id = int(time.time())
        self._poll_count = 0

    # ── identity / config ────────────────────────────────────────────────────
    def is_configured(self) -> bool:
        return True

    def get_token(self) -> str:
        return self._token

    def get_headers(self, accept: str = "application/json") -> dict:
        return {
            "Authorization": "Bearer mock-token",
            "Accept": accept,
            "Content-Type": "application/json",
            "X-Mock-Mode": "true",
        }

    @property
    def token_status(self) -> dict:
        return {"valid": True, "expires_in_minutes": 55}

    # ── REST ─────────────────────────────────────────────────────────────────
    def get_available_resources(self) -> list:
        return [dict(r) for r in fixtures.AVAILABLE_RESOURCES]

    def get_cn_available_resources(self) -> list:
        return [dict(r) for r in fixtures.CN_RESOURCES]

    def get_resource(self, resource: str, params: dict | None = None, version: str | None = None):
        return [dict(p) for p in fixtures.RESOURCE_PAYLOADS.get(resource, [])]

    def get_resource_by_id(self, resource: str, guid: str) -> tuple[dict, str]:
        sample = fixtures.RESOURCE_PAYLOADS.get(resource) or [{}]
        body = dict(sample[0])
        body["id"] = guid
        version = "application/vnd.hedtech.integration.v16+json"
        return body, version

    # ── bus ──────────────────────────────────────────────────────────────────
    def consume_messages(self, limit: int = 20, last_processed_id: int | None = None) -> list:
        # Deterministic trickle: one new message per poll. last_processed_id
        # is honored so the Replay tab "Fetch by ID" returns a stable result.
        if last_processed_id is not None:
            template = next(self._stream)
            msg = dict(template)
            msg["id"] = int(last_processed_id) + 1
            msg["publishedOn"] = self._iso_now()
            return [msg]

        self._poll_count += 1
        template = next(self._stream)
        self._next_id += 1
        msg = dict(template)
        msg["id"] = self._next_id
        msg["publishedOn"] = self._iso_now()
        return [msg]

    def get_queue_depth(self) -> int:
        # Predictably fluctuates between 0 and 19 — looks "alive" without random.
        return self._poll_count % 20

    # ── publish (caustic in real mode; no-op echo in mock) ───────────────────
    def publish_notification(self, notification: dict) -> dict:
        return {"status": "accepted", "mock": True, "echo": notification.get("resource", {})}

    # ── GraphQL ──────────────────────────────────────────────────────────────
    def graphql(self, query: str, variables: dict | None = None) -> dict:
        if "__schema" in query and ("queryType" in query or "types" in query):
            return {"data": {"__schema": fixtures.INTROSPECTION_SCHEMA}}

        # Best-effort canned response for the seeded GraphQL examples — the
        # editor renders a non-empty JSON body so the demo flow is visible.
        return {
            "data": {
                "_mock": True,
                "_disclaimer": "CONSOLE_MOCK_MODE — no GraphQL call was made.",
                "variables": variables or {},
            }
        }

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _iso_now() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
