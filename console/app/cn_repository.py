"""Direct in-process source of change-notification configuration data.

Replaces the HTTP proxy to the C# CNM service. Method shape is preserved
1:1 so the /api/cn/* routes are a thin pass-through.

The Colleague Web API reads (list, detail, paragraph) are intentionally
stubbed pending endpoint confirmation — same state the C# Infrastructure
ChangeNotificationRepository was in. The set-diff diagnostics is fully
functional because the inputs (Ethos resources + the CN list shape) are
known.
"""
from __future__ import annotations

from typing import Any


class CnRepository:
    """Real-mode CN repository — talks (or will talk) to Colleague Web API.

    Mock-mode swaps this for MockCnRepository at app-creation time.
    """

    def __init__(self, colleague_api_client):
        self._colleague = colleague_api_client

    # ── identity ─────────────────────────────────────────────────────────────
    def is_configured(self) -> bool:
        return self._colleague.is_configured()

    # ── health ───────────────────────────────────────────────────────────────
    def get_health(self) -> dict:
        # No external CNM service to ping anymore. Report the inputs that
        # the CN tab actually depends on, so the operator sees what's live.
        return {
            "status": "ok",
            "service": "ethos-console.cn",
            "colleague_api_configured": self._colleague.is_configured(),
        }

    # ── change-notification reads ────────────────────────────────────────────
    # TODO: implement once Colleague Web API CN-config endpoints are confirmed.
    # Same state the C# Infrastructure ChangeNotificationRepository was in.
    def get_notifications(self, resource: str | None = None, status: str | None = None) -> list:
        return []

    def get_notification(self, cn_id: str) -> dict | None:
        return None

    def get_paragraph(self, cn_id: str) -> dict | None:
        return None

    # ── diagnostics — fully functional ───────────────────────────────────────
    def get_diagnostics(self, subscribed_names: list[str]) -> dict:
        """Subscribed-vs-published set diff.

        `subscribed_names` is what the Ethos tenant is subscribed to (from
        get_available_resources). The published side is whatever
        get_notifications returns. Caller assembles inputs so this method
        stays cheap and testable.
        """
        published = {n.get("resourceName") for n in self.get_notifications() if n.get("resourceName")}
        subscribed = set(subscribed_names or [])
        return {
            "aligned":               sorted(subscribed & published),
            "subscribedNotPublished": sorted(subscribed - published),
            "publishedNotSubscribed": sorted(published - subscribed),
            "totalSubscribed":       len(subscribed),
            "totalPublished":        len(published),
        }
