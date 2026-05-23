"""Mock ConductorClient. Active only when CONSOLE_MOCK_MODE=true."""
from app.conductor_client import ConductorClient
from . import fixtures


class MockConductorClient(ConductorClient):
    def __init__(self):
        super().__init__(base_url="https://mock.conductor.local")

    def is_configured(self) -> bool:
        return True

    def trigger_workflow(self, name: str, payload: dict, base_url: str | None = None) -> str:
        return fixtures.conductor_trigger_id(name)
