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
    data = hm.check_health()
    data["mock"] = bool(current_app.extensions.get("mock_mode"))
    return jsonify(data)


@health_bp.get("/token")
def token_status():
    """Lightweight token status — polled by the expiry warning banner."""
    ethos = get_ethos(current_app._get_current_object())
    return jsonify(ethos.token_status)


@health_bp.post("/caches/refresh")
@api_auth_required
def refresh_caches():
    """Drop every introspection-derived cache the console shares across tabs.
    Cheap; the next request rebuilds against the active Ethos environment.
    Useful when Ethos-side config changed mid-session or when debugging.
    """
    import app.routes.graphql_routes as gr
    import app.routes.resources as rr
    gr._schema_cache = None
    gr._schema_cache_time = 0.0
    rr._resource_cache = []
    rr._resource_source = ""
    rr._cn_resource_cache = []
    return jsonify({
        "refreshed": True,
        "cleared": ["graphql_schema", "available_resources", "cn_resources"],
    })
