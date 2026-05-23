"""Proxy routes that surface CNM API data in the Ethos Dev Console.

All routes return 503 with a setup guide when CNM_BASE_URL is not set.
CNM errors (network, HTTP 4xx/5xx) are surfaced as 502 with the original
message so the frontend can display them inline rather than crashing.
"""
from flask import Blueprint, jsonify, request, current_app
from app.auth import api_auth_required
from app.cn_client import CnmClient

cn_bp = Blueprint("cn_monitor", __name__)


def _get_cnm() -> CnmClient:
    return current_app.extensions["cnm_client"]


def _require_cnm():
    client = _get_cnm()
    if not client.is_configured():
        return None, jsonify({
            "error": "CNM service not configured",
            "setup": (
                "Set CNM_BASE_URL in .env to enable this tab. "
                "Example: CNM_BASE_URL=http://localhost:5000 (dev) or "
                "https://your-host/prod/cnm (production). "
                "Set CNM_API_KEY to a Bearer token for production (leave empty in dev)."
            ),
        }), 503
    return client, None, None


# ── Health ────────────────────────────────────────────────────────────────────

@cn_bp.get("/health")
@api_auth_required
def cnm_health():
    client, err, code = _require_cnm()
    if err:
        return err, code
    try:
        return jsonify(client.get_health())
    except Exception as exc:
        return jsonify({"error": str(exc), "status": "unreachable"}), 502


# ── Change notifications ──────────────────────────────────────────────────────

@cn_bp.get("/notifications")
@api_auth_required
def list_notifications():
    client, err, code = _require_cnm()
    if err:
        return err, code
    resource = request.args.get("resource")
    status = request.args.get("status")
    try:
        items = client.get_notifications(resource=resource, status=status)
        return jsonify({"items": items, "total": len(items)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@cn_bp.get("/notifications/<cn_id>")
@api_auth_required
def get_notification(cn_id: str):
    client, err, code = _require_cnm()
    if err:
        return err, code
    try:
        return jsonify(client.get_notification(cn_id))
    except Exception as exc:
        status = 404 if "404" in str(exc) else 502
        return jsonify({"error": str(exc)}), status


@cn_bp.get("/notifications/<cn_id>/paragraph")
@api_auth_required
def get_paragraph(cn_id: str):
    client, err, code = _require_cnm()
    if err:
        return err, code
    try:
        return jsonify(client.get_paragraph(cn_id))
    except Exception as exc:
        status = 404 if "404" in str(exc) else 502
        return jsonify({"error": str(exc)}), status


@cn_bp.get("/notifications/<cn_id>/history")
@api_auth_required
def get_cn_history(cn_id: str):
    client, err, code = _require_cnm()
    if err:
        return err, code
    try:
        items = client.get_cn_history(cn_id)
        return jsonify({"items": items})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


# ── Diagnostics ───────────────────────────────────────────────────────────────

@cn_bp.get("/diagnostics")
@api_auth_required
def diagnostics():
    client, err, code = _require_cnm()
    if err:
        return err, code
    try:
        return jsonify(client.get_diagnostics())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


# ── Push change notifications ─────────────────────────────────────────────────

@cn_bp.post("/push")
@api_auth_required
def push_notifications():
    app = current_app._get_current_object()
    ethos = app.extensions.get("ethos_client")
    if not ethos or not ethos.is_configured():
        return jsonify({"error": "Ethos not configured", "setup": "Set ETHOS_API_KEY in .env"}), 503

    data = request.get_json(silent=True) or {}
    resource_name = (data.get("resource_name") or "").strip()
    operation = data.get("operation", "replaced")
    guids = [g.strip() for g in (data.get("guids") or []) if str(g).strip()]

    if not resource_name:
        return jsonify({"error": "resource_name is required"}), 400
    if not guids:
        return jsonify({"error": "at least one guid is required"}), 400

    results = []
    for guid in guids:
        try:
            body, version = ethos.get_resource_by_id(resource_name, guid)
            notification = {
                "resource": {"name": resource_name, "id": guid, "version": version},
                "operation": operation,
                "contentType": "resource-representation",
                "content": body,
            }
            ethos.publish_notification(notification)
            results.append({"guid": guid, "status": "success", "version": version})
        except Exception as exc:
            results.append({"guid": guid, "status": "error", "error": str(exc), "version": None})

    return jsonify({"results": results})


# ── Audit log ─────────────────────────────────────────────────────────────────

@cn_bp.get("/audit-log")
@api_auth_required
def audit_log():
    client, err, code = _require_cnm()
    if err:
        return err, code
    try:
        data = client.get_audit_log(
            page=int(request.args.get("page", 1)),
            page_size=int(request.args.get("pageSize", 50)),
            user_id=request.args.get("userId"),
            target_identifier=request.args.get("targetIdentifier"),
        )
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
