from flask import Blueprint, jsonify, current_app
from app import get_health_monitor, get_ethos, get_edge_gate

health_bp = Blueprint("health", __name__)


@health_bp.get("/live")
def liveness():
    """Cheap liveness probe — always 200 if the process is up."""
    return jsonify({"status": "ok"}), 200


@health_bp.get("/")
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


@health_bp.get("/edge-gate")
def edge_gate_health():
    """DoaneEdgeGate's own /health, proxied for the Health tab tile. Polled
    separately from the main health payload so a slow/unreachable gate can
    never hold up the token/queue/latency/error tiles above it.
    """
    gate = get_edge_gate(current_app._get_current_object())
    return jsonify(gate.check_health())


@health_bp.post("/caches/refresh")
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
