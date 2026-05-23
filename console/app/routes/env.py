from flask import Blueprint, jsonify, request, current_app
from app.auth import api_auth_required

env_bp = Blueprint("env", __name__)


@env_bp.get("/")
@api_auth_required
def list_environments():
    envs = current_app.config.get("ETHOS_ENVIRONMENTS", [])
    current = current_app.extensions.get("current_env_name", "")
    return jsonify({
        "environments": [{"name": e["name"], "url": e["url"]} for e in envs],
        "current": current,
    })


@env_bp.post("/switch")
@api_auth_required
def switch_environment():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    envs = current_app.config.get("ETHOS_ENVIRONMENTS", [])
    env = next((e for e in envs if e["name"] == name), None)
    if not env:
        return jsonify({"error": f"Environment '{name}' not found"}), 404

    ethos = current_app.extensions["ethos_client"]
    ethos.api_key = env["key"]
    ethos.base_url = env["url"].rstrip("/")
    ethos._token = None
    ethos._token_expiry = None

    monitor = current_app.extensions.get("bus_monitor")
    if monitor:
        monitor.reset()

    # Schemas differ between environments — drop the introspection cache so
    # the next GraphQL/Schema-Browser request refetches against the new env.
    import app.routes.graphql_routes as gr
    gr._schema_cache = None
    gr._schema_cache_time = 0.0

    current_app.extensions["current_env_name"] = name
    return jsonify({"switched_to": name, "url": env["url"]})
