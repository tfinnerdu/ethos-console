from flask import Blueprint, jsonify, request, current_app
from app import get_ethos

resources_bp = Blueprint("resources", __name__)

_resource_cache: list = []
_cn_resource_cache: list = []


@resources_bp.get("/")
def list_resources():
    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured", "items": []}), 200

    global _resource_cache
    if not _resource_cache:
        try:
            _resource_cache = ethos.get_available_resources()
        except Exception as exc:
            return jsonify({"error": str(exc), "items": []}), 200

    return jsonify({"items": _resource_cache, "count": len(_resource_cache)})


@resources_bp.get("/cn-enabled")
def cn_enabled_resources():
    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured", "items": []}), 200

    global _cn_resource_cache
    if not _cn_resource_cache:
        try:
            _cn_resource_cache = ethos.get_cn_available_resources()
        except Exception as exc:
            return jsonify({"error": str(exc), "items": []}), 200

    return jsonify({"items": _cn_resource_cache, "count": len(_cn_resource_cache)})


@resources_bp.post("/refresh")
def refresh_cache():
    global _resource_cache, _cn_resource_cache
    _resource_cache = []
    _cn_resource_cache = []
    return jsonify({"refreshed": True})


@resources_bp.post("/graphql")
def graphql_proxy():
    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured"}), 503
    data = request.get_json(force=True)
    try:
        result = ethos.graphql(data.get("query", ""), data.get("variables"))
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
