import os
import requests
from flask import Blueprint, jsonify, request, current_app
from app import get_ethos
from app.database import db, ReplayHistory

replay_bp = Blueprint("replay", __name__)


@replay_bp.post("/fetch")
def fetch_message():
    data = request.get_json(force=True)
    message_id = data.get("message_id")
    if not message_id:
        return jsonify({"error": "message_id is required"}), 400

    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured"}), 503

    try:
        last_id = int(message_id) - 1
        messages = ethos.consume_messages(limit=1, last_processed_id=last_id)
        if not messages:
            return jsonify({"error": "Message not found or already consumed past this point"}), 404
        return jsonify({"message": messages[0]})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@replay_bp.post("/trigger")
def trigger_replay():
    data = request.get_json(force=True)
    payload = data.get("payload")
    workflow_name = data.get("workflow_name")
    conductor_url = data.get("conductor_url") or current_app.config.get("CONDUCTOR_URL", "")
    conductor_key = current_app.config.get("CONDUCTOR_API_KEY", "")

    if not payload:
        return jsonify({"error": "payload is required"}), 400
    if not workflow_name:
        return jsonify({"error": "workflow_name is required"}), 400
    if not conductor_url:
        return jsonify({"error": "conductor_url is required"}), 400

    resource_name = payload.get("resource", {}).get("name", "unknown")
    operation = payload.get("resource", {}).get("operation", "unknown")
    source_id = str(payload.get("id", ""))

    history_entry = ReplayHistory(
        source_message_id=source_id,
        resource_name=resource_name,
        operation=operation,
        workflow_name=workflow_name,
        conductor_url=conductor_url,
    )

    try:
        headers = {"Content-Type": "application/json"}
        if conductor_key:
            headers["X-Authorization"] = conductor_key

        r = requests.post(
            f"{conductor_url.rstrip('/')}/api/workflow/{workflow_name}",
            headers=headers,
            json={
                "resource": payload.get("resource"),
                "content": payload.get("content", {}),
            },
            timeout=30,
        )
        r.raise_for_status()
        workflow_id = r.text.strip().strip('"')

        history_entry.conductor_workflow_id = workflow_id
        history_entry.outcome = "success"
        db.session.add(history_entry)
        db.session.commit()

        return jsonify({
            "workflow_id": workflow_id,
            "outcome": "success",
            "conductor_workflow_url": f"{conductor_url.rstrip('/')}/api/workflow/{workflow_id}",
        })
    except requests.HTTPError as exc:
        history_entry.outcome = "error"
        history_entry.error_message = str(exc)
        db.session.add(history_entry)
        db.session.commit()
        return jsonify({"error": str(exc), "outcome": "error"}), 502
    except Exception as exc:
        history_entry.outcome = "error"
        history_entry.error_message = str(exc)
        db.session.add(history_entry)
        db.session.commit()
        return jsonify({"error": str(exc), "outcome": "error"}), 500


@replay_bp.get("/history")
def replay_history():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 25))
    entries = ReplayHistory.query.order_by(ReplayHistory.replayed_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        "items": [e.to_dict() for e in entries.items],
        "total": entries.total,
        "page": page,
        "pages": entries.pages,
    })
