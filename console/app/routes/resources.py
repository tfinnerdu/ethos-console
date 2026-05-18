from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, current_app
from app import get_ethos
from app.database import db, ResourceAnnotation

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


@resources_bp.get("/<name>")
def resource_detail(name: str):
    annotation = ResourceAnnotation.query.filter_by(resource_name=name).first()
    cn_supported = name in _cn_resource_cache if _cn_resource_cache else None
    available = name in _resource_cache if _resource_cache else None
    return jsonify({
        "name": name,
        "cn_supported": cn_supported,
        "annotation": annotation.to_dict() if annotation else None,
        "available": available,
    })


@resources_bp.put("/<name>/annotate")
def annotate_resource(name: str):
    data = request.get_json(force=True) or {}
    annotation = ResourceAnnotation.query.filter_by(resource_name=name).first()
    if annotation is None:
        annotation = ResourceAnnotation(resource_name=name)
        db.session.add(annotation)

    if "trigger_conditions_gap" in data:
        annotation.trigger_conditions_gap = bool(data["trigger_conditions_gap"])
    if "notes" in data:
        annotation.notes = data["notes"]
    if "updated_by" in data:
        annotation.updated_by = data["updated_by"]
    annotation.last_updated = datetime.now(timezone.utc)

    db.session.commit()
    return jsonify(annotation.to_dict())


@resources_bp.get("/annotations")
def list_annotations():
    annotations = ResourceAnnotation.query.order_by(ResourceAnnotation.resource_name).all()
    return jsonify({"items": [a.to_dict() for a in annotations]})
