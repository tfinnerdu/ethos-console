"""Mock CnRepository. Active only when CONSOLE_MOCK_MODE=true."""
from app.cn_repository import CnRepository
from . import fixtures


class MockCnRepository(CnRepository):
    def __init__(self):
        # No real colleague client needed — every method serves fixtures.
        super().__init__(colleague_api_client=None)

    def is_configured(self) -> bool:
        return True

    def get_health(self) -> dict:
        return {
            "status": "ok",
            "service": "ethos-console.cn",
            "colleague_api_configured": True,
            "mock": True,
        }

    def get_notifications(self, resource: str | None = None, status: str | None = None) -> list:
        items = fixtures.cnm_notifications()
        if resource:
            items = [n for n in items if resource.lower() in n["resourceName"].lower()]
        if status:
            items = [n for n in items if n["status"].lower() == status.lower()]
        return items

    def get_notification(self, cn_id: str) -> dict | None:
        for n in fixtures.cnm_notifications():
            if n["id"] == cn_id:
                detail = dict(n)
                detail["description"] = "Mock change notification — no Colleague call was made."
                detail["edpsRules"] = ["MOCK.RULE.1", "MOCK.RULE.2"]
                return detail
        return None

    def get_paragraph(self, cn_id: str) -> dict | None:
        return {
            "id": cn_id,
            "paragraphCode": "MOCK.PARA",
            "source": "* CONSOLE_MOCK_MODE — no paragraph fetched\nDISPLAY 'mock'",
            "_mock": True,
        }

    def get_diagnostics(self, subscribed_names: list[str]) -> dict:
        # Mock returns a self-consistent fixture so the UI shows a non-empty
        # diff regardless of what `subscribed_names` was.
        return dict(fixtures.CNM_DIAGNOSTICS) | {
            "totalSubscribed": len(fixtures.CNM_DIAGNOSTICS["aligned"]) + len(fixtures.CNM_DIAGNOSTICS["subscribedNotPublished"]),
            "totalPublished":  len(fixtures.CNM_DIAGNOSTICS["aligned"]) + len(fixtures.CNM_DIAGNOSTICS["publishedNotSubscribed"]),
        }
