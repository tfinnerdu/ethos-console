from flask import Blueprint, jsonify, current_app
from app import get_health_monitor

health_bp = Blueprint("health", __name__)


@health_bp.get("/live")
def liveness():
    """Cheap liveness probe — always 200 if the process is up."""
    return jsonify({"status": "ok"}), 200


@health_bp.get("/")
def health_check():
    hm = get_health_monitor(current_app._get_current_object())
    return jsonify(hm.check_health())
