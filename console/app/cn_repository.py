"""Direct in-process source of change-notification configuration data.

Replaces the HTTP proxy to the C# CNM service. Method shape is preserved
1:1 so the /api/cn/* routes are a thin pass-through.

The Colleague Web API reads (list, detail, paragraph) call the real
/api/event-configurations endpoint via ColleagueApiClient — this is a live
Colleague Web API call, not a stub. Field-name mapping in get_notifications()
is best-effort against the documented shape (see the comment there); adjust
if a real tenant returns different keys. The set-diff diagnostics is fully
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
    # Routed through the Colleague Web API event-configurations endpoint —
    # /api/event-configurations returns the live CN configuration. The
    # field-name mapping below is best-effort against the documented shape;
    # adjust if a real tenant returns different keys.
    def get_notifications(self, resource: str | None = None, status: str | None = None) -> list:
        if not self._colleague or not self._colleague.is_configured():
            return []
        configs = self._colleague.get_event_configurations(resource_name=resource) or []
        items = []
        for c in configs:
            normalised = {
                "id": str(c.get("id") or f"CN-{c.get('resourceName') or 'unknown'}"),
                "resourceName": c.get("resourceName") or c.get("resource") or "",
                "status": "Enabled" if c.get("isEnabled", c.get("enabled")) else "Disabled",
                "hasParagraph": bool(c.get("paragraphCode") or c.get("paragraph")),
                "paragraphCode": c.get("paragraphCode") or c.get("paragraph"),
                "processCode": c.get("processCode"),
                "lastModified": c.get("lastModified") or c.get("modifiedOn"),
            }
            if status and normalised["status"].lower() != status.lower():
                continue
            items.append(normalised)
        return items

    def get_notification(self, cn_id: str) -> dict | None:
        if not self._colleague or not self._colleague.is_configured():
            return None
        for item in self.get_notifications():
            if item["id"] == cn_id:
                # Colleague Web API doesn't expose per-CN detail in a separate
                # endpoint — the list entry IS the detail. Return as-is.
                return item
        return None

    def get_paragraph(self, cn_id: str) -> dict | None:
        # Paragraph source isn't surfaced by /api/event-configurations.
        # Until a Colleague Web API endpoint for paragraph source is wired
        # up, return the paragraph code (if known) so the UI can render the
        # name even when source text isn't available.
        item = self.get_notification(cn_id)
        if not item or not item.get("paragraphCode"):
            return None
        return {
            "id": cn_id,
            "paragraphCode": item["paragraphCode"],
            "source": None,  # TODO: source endpoint TBD
        }

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
