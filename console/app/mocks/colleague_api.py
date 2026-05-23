"""Mock ColleagueApiClient. Active only when CONSOLE_MOCK_MODE=true."""
from app.colleague_api_client import ColleagueApiClient
from . import fixtures


class MockColleagueApiClient(ColleagueApiClient):
    def __init__(self):
        super().__init__(base_url="https://mock.colleague.local", username="mock", password="mock")

    def is_configured(self) -> bool:
        return True

    def get_about(self) -> dict:
        return dict(fixtures.COLLEAGUE_ABOUT)

    def get_event_configurations(self, resource_name: str | None = None) -> list:
        items = list(fixtures.COLLEAGUE_EVENT_CONFIGS)
        if resource_name:
            items = [c for c in items if resource_name.lower() in c["resourceName"].lower()]
        return items

    def call_transaction(self, transaction_id: str, payload: dict) -> dict:
        return fixtures.colleague_transaction_result(transaction_id, payload)

    def get_metadata_manifest(self, api_domain: str, api_type: str) -> dict:
        manifest = dict(fixtures.COLLEAGUE_METADATA_MANIFEST)
        manifest["ApiDomain"] = api_domain
        manifest["ApiType"] = api_type
        return manifest
