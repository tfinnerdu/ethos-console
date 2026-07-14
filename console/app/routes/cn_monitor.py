"""Change-notification monitor routes — in-process, no proxy hop.

Folded from the previous C# CNM service. Real-mode reads against Colleague
Web API are routed through `app.cn_repository.CnRepository`; mock mode
swaps it for `MockCnRepository`. Audit emission lives in `app.audit`.
"""
from flask import Blueprint, jsonify, request, current_app
from app.audit import Action, Outcome, write_event, query_events
from app.cn_repository import CnRepository

cn_bp = Blueprint("cn_monitor", __name__)


def _get_repo() -> CnRepository:
    return current_app.extensions["cn_repository"]


# ── Health ────────────────────────────────────────────────────────────────────

@cn_bp.get("/health")
def cnm_health():
    return jsonify(_get_repo().get_health())


# ── Change notifications ──────────────────────────────────────────────────────

@cn_bp.get("/notifications")
def list_notifications():
    resource = request.args.get("resource")
    status = request.args.get("status")
    try:
        items = _get_repo().get_notifications(resource=resource, status=status)
        return jsonify({"items": items, "total": len(items)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@cn_bp.get("/notifications/<cn_id>")
def get_notification(cn_id: str):
    try:
        detail = _get_repo().get_notification(cn_id)
        if not detail:
            return jsonify({"error": f"notification '{cn_id}' not found"}), 404
        write_event(Action.VIEW, "cn.notification", cn_id)
        return jsonify(detail)
    except Exception as exc:
        status = 404 if "404" in str(exc) else 502
        return jsonify({"error": str(exc)}), status


@cn_bp.get("/notifications/<cn_id>/paragraph")
def get_paragraph(cn_id: str):
    try:
        paragraph = _get_repo().get_paragraph(cn_id)
        if not paragraph:
            return jsonify({"error": f"paragraph for '{cn_id}' not found"}), 404
        write_event(Action.VIEW, "cn.paragraph", cn_id)
        return jsonify(paragraph)
    except Exception as exc:
        status = 404 if "404" in str(exc) else 502
        return jsonify({"error": str(exc)}), status


@cn_bp.get("/notifications/<cn_id>/history")
def get_cn_history(cn_id: str):
    """History for a single CN is whatever the audit log says about it."""
    data = query_events(page=1, page_size=200, resource_id=cn_id)
    return jsonify({"items": data["items"]})


# ── Diagnostics ───────────────────────────────────────────────────────────────

@cn_bp.get("/diagnostics")
def diagnostics():
    """Subscribed-vs-published set diff.

    Subscribed = Ethos's CN-available-resources list (what the tenant is
    set up to receive).  Published = whatever the CN repository says is
    configured to fire.
    """
    ethos = current_app.extensions.get("ethos_client")
    subscribed = []
    if ethos and ethos.is_configured():
        try:
            subscribed = [
                r.get("resourceName") or r.get("name")
                for r in (ethos.get_cn_available_resources() or [])
                if r
            ]
            subscribed = [n for n in subscribed if n]
        except Exception:
            subscribed = []
    try:
        return jsonify(_get_repo().get_diagnostics(subscribed))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


# ── Push change notifications ─────────────────────────────────────────────────

@cn_bp.post("/push")
def push_notifications():
    app_obj = current_app._get_current_object()
    ethos = app_obj.extensions.get("ethos_client")
    if not ethos or not ethos.is_configured():
        return jsonify({"error": "Ethos not configured", "setup": "Add an ETHOS_ENV_1_* block to .env"}), 503

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

    successes = sum(1 for r in results if r["status"] == "success")
    failures = len(results) - successes
    outcome = (
        Outcome.SUCCESS if failures == 0
        else Outcome.FAILURE if successes == 0
        else Outcome.PARTIAL
    )
    # One audit row for the whole publish operation — never one per guid.
    write_event(
        Action.PUBLISH, "ethos.change_notification", resource_name,
        outcome=outcome,
        detail={"operation": operation, "guid_count": len(guids), "successes": successes, "failures": failures},
    )
    return jsonify({"results": results})


# ── Audit log ─────────────────────────────────────────────────────────────────

@cn_bp.get("/audit-log")
def audit_log():
    try:
        data = query_events(
            page=int(request.args.get("page", 1)),
            page_size=int(request.args.get("pageSize", 50)),
            actor=request.args.get("userId"),
            resource_id=request.args.get("targetIdentifier"),
        )
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
