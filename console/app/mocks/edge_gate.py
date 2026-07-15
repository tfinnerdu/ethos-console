"""Mock EdgeGateClient. Active only when CONSOLE_MOCK_MODE=true."""
from app.edge_gate_client import EdgeGateClient


class MockEdgeGateClient(EdgeGateClient):
    def __init__(self):
        super().__init__(base_url="https://mock.edge-gate.local")

    def is_configured(self) -> bool:
        return True

    def check_health(self) -> dict:
        return {
            "configured": True,
            "reachable": True,
            "status": "ok",
            "service": "DoaneEdgeGate",
            "version": "mock",
            "uptime_seconds": 3600,
        }
