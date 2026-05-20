from flask import Blueprint, jsonify, current_app
from app import get_health_monitor, get_ethos
from app.auth import api_auth_required

health_bp = Blueprint("health", __name__)


@health_bp.get("/live")
def liveness():
    """Cheap liveness probe — always 200 if the process is up."""
    return jsonify({"status": "ok"}), 200


@health_bp.get("/")
@api_auth_required
def health_check():
    hm = get_health_monitor(current_app._get_current_object())
    return jsonify(hm.check_health())


@health_bp.get("/token")
def token_status():
    """Lightweight token status — polled by the expiry warning banner."""
    ethos = get_ethos(current_app._get_current_object())
    return jsonify(ethos.token_status)
