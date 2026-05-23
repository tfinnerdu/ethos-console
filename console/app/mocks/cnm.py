"""Mock CnmClient. Active only when CONSOLE_MOCK_MODE=true."""
from app.cn_client import CnmClient
from . import fixtures


class MockCnmClient(CnmClient):
    def __init__(self):
        super().__init__(base_url="https://mock.cnm.local")

    def is_configured(self) -> bool:
        return True

    def get_health(self) -> dict:
        return dict(fixtures.CNM_HEALTH)

    def get_notifications(self, resource: str | None = None, status: str | None = None) -> list:
        items = fixtures.cnm_notifications()
        if resource:
            items = [n for n in items if resource.lower() in n["resourceName"].lower()]
        if status:
            items = [n for n in items if n["status"].lower() == status.lower()]
        return items

    def get_notification(self, cn_id: str) -> dict:
        for n in fixtures.cnm_notifications():
            if n["id"] == cn_id:
                detail = dict(n)
                detail["description"] = "Mock change notification — no Colleague call was made."
                detail["edpsRules"] = ["MOCK.RULE.1", "MOCK.RULE.2"]
                detail["recentHistory"] = []
                return detail
        return {"error": f"notification '{cn_id}' not found", "_mock": True}

    def get_paragraph(self, cn_id: str) -> dict:
        return {
            "id": cn_id,
            "paragraphCode": "MOCK.PARA",
            "source": "* CONSOLE_MOCK_MODE — no paragraph fetched\nDISPLAY 'mock'",
            "_mock": True,
        }

    def get_cn_history(self, cn_id: str) -> list:
        return [
            {"timestamp": "2026-05-22T11:00:00Z", "action": "Viewed",   "actor": "mock-user"},
            {"timestamp": "2026-05-21T09:30:00Z", "action": "Modified", "actor": "mock-user"},
        ]

    def get_diagnostics(self) -> dict:
        return dict(fixtures.CNM_DIAGNOSTICS)

    def get_audit_log(
        self,
        page: int = 1,
        page_size: int = 50,
        user_id: str | None = None,
        target_identifier: str | None = None,
    ) -> dict:
        items = list(fixtures.CNM_AUDIT_LOG["items"])
        if user_id:
            items = [r for r in items if user_id.lower() in r["userId"].lower()]
        if target_identifier:
            items = [r for r in items if target_identifier.lower() in r["targetIdentifier"].lower()]
        return {
            "items": items,
            "page": page,
            "pageSize": page_size,
            "totalPages": 1,
            "totalCount": len(items),
        }
