"""Thin HTTP client for the EthosCn CNM API.

Set CNM_BASE_URL (e.g. http://localhost:5000 or https://host/prod/cnm).
Set CNM_API_KEY to the Bearer token for production (Azure AD service token).
Leave CNM_API_KEY empty for dev — CNM's DevAuth accepts unauthenticated calls.

All methods raise on HTTP errors so callers can catch and return 502.
"""
import requests


class CnmClient:
    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.base_url)

    # ── internal ──────────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def _get(self, path: str, params: dict | None = None, timeout: int = 15):
        r = requests.get(
            f"{self.base_url}/api/v1{path}",
            headers=self._headers(),
            params={k: v for k, v in (params or {}).items() if v is not None},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()

    # ── health ────────────────────────────────────────────────────────────────

    def get_health(self) -> dict:
        return self._get("/health")

    # ── change notifications ──────────────────────────────────────────────────

    def get_notifications(self, resource: str | None = None, status: str | None = None) -> list:
        return self._get("/change-notifications", params={"resource": resource, "status": status})

    def get_notification(self, cn_id: str) -> dict:
        return self._get(f"/change-notifications/{cn_id}")

    def get_paragraph(self, cn_id: str) -> dict:
        return self._get(f"/change-notifications/{cn_id}/paragraph")

    def get_cn_history(self, cn_id: str) -> list:
        return self._get(f"/change-notifications/{cn_id}/history")

    # ── diagnostics ───────────────────────────────────────────────────────────

    def get_diagnostics(self) -> dict:
        return self._get("/diagnostics/subscription-publishing")

    # ── audit log ─────────────────────────────────────────────────────────────

    def get_audit_log(
        self,
        page: int = 1,
        page_size: int = 50,
        user_id: str | None = None,
        target_identifier: str | None = None,
    ) -> dict:
        return self._get("/audit-log", params={
            "page": page,
            "pageSize": page_size,
            "userId": user_id,
            "targetIdentifier": target_identifier,
        })
