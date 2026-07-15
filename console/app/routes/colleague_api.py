from flask import Blueprint, jsonify, request, current_app
from app.audit import Action, Outcome, write_event
from app.request_utils import get_json_body

colleague_api_bp = Blueprint("colleague_api", __name__)


def _get_client():
    return current_app.extensions["colleague_api_client"]


def _require_configured():
    client = _get_client()
    if not client.is_configured():
        return None, (jsonify({
            "error": "Colleague Web API not configured",
            "setup": (
                "Set COLLEAGUE_WEB_API_URL, COLLEAGUE_WEB_API_USER, "
                "and COLLEAGUE_WEB_API_PASS in .env"
            ),
        }), 503)
    return client, None


@colleague_api_bp.get("/about")
def get_about():
    client, err = _require_configured()
    if err:
        return err
    try:
        return jsonify(client.get_about())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@colleague_api_bp.get("/event-configurations")
def get_event_configs():
    client, err = _require_configured()
    if err:
        return err
    resource_name = request.args.get("resourceName")
    try:
        data = client.get_event_configurations(resource_name)
        return jsonify(data if isinstance(data, list) else [])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@colleague_api_bp.post("/transaction")
def call_transaction():
    client, err = _require_configured()
    if err:
        return err
    data = get_json_body(request)
    transaction_id = (data.get("transactionId") or "").strip().upper()
    payload = data.get("payload") or {}
    if not transaction_id:
        return jsonify({"error": "transactionId is required"}), 400
    try:
        result = client.call_transaction(transaction_id, payload)
        write_event(Action.CALL, "colleague_ctx_transaction", transaction_id)
        return jsonify(result)
    except Exception as exc:
        write_event(
            Action.CALL, "colleague_ctx_transaction", transaction_id,
            outcome=Outcome.FAILURE, failure_reason=str(exc),
        )
        return jsonify({"error": str(exc)}), 500


@colleague_api_bp.get("/metadata/<api_domain>/<api_type>")
def get_metadata(api_domain: str, api_type: str):
    client, err = _require_configured()
    if err:
        return err
    try:
        return jsonify(client.get_metadata_manifest(api_domain, api_type))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
