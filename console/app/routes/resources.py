from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, current_app
from app import get_ethos
from app.database import db, ResourceAnnotation

resources_bp = Blueprint("resources", __name__)

_resource_cache: list = []
_resource_source: str = ""  # "available-resources" or "graphql-schema"
_cn_resource_cache: list = []


def _populate_resource_cache(ethos) -> tuple[list, str, str | None]:
    """Resolve the resource list via GraphQL introspection.

    Parked: /api/available-resources is a meta endpoint whose access is gated
    by application type/role on the Ethos side, and tenant configuration for
    it varies enough that we hit 401/404 cases that aren't ours to fix.
    GraphQL introspection exposes the same data — query field names →
    camelCase resource, trailing digits → version — so we use that as the
    sole source until the REST path is sorted out tenant-side.

    `EthosClient.get_available_resources()` is intentionally left in place
    for direct diagnostic use and so the future-revisit path is one
    `ethos.get_available_resources()` call away. It just isn't wired here.

    Reuses the introspection schema cache shared with the Schema Browser and
    GraphQL tab so this is free when those tabs have been visited first.
    """
    import time as _time
    from app.routes import graphql_routes as gr
    from app.routes.graphql_routes import (
        INTROSPECTION_QUERY,
        SCHEMA_CACHE_TTL,
        _resources_from_graphql_schema,
    )

    schema = None
    cached = gr._schema_cache
    if (
        cached is not None
        and cached.get("_source") != "available-resources"
        and (_time.time() - gr._schema_cache_time) < SCHEMA_CACHE_TTL
    ):
        schema = cached
    else:
        result = ethos.graphql(INTROSPECTION_QUERY)
        schema = (result.get("data") or {}).get("__schema")
        if schema:
            gr._schema_cache = schema
            gr._schema_cache_time = _time.time()

    if not schema:
        raise RuntimeError("GraphQL introspection returned no schema.")

    return _resources_from_graphql_schema(schema), "graphql-schema", None


@resources_bp.get("/")
def list_resources():
    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured", "items": []}), 200

    global _resource_cache, _resource_source
    note = None
    if not _resource_cache:
        try:
            _resource_cache, _resource_source, note = _populate_resource_cache(ethos)
        except Exception as exc:
            return jsonify({"error": str(exc), "items": []}), 200

    payload = {
        "items": _resource_cache,
        "count": len(_resource_cache),
        "source": _resource_source,
    }
    if note:
        payload["note"] = note
    return jsonify(payload)


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
    global _resource_cache, _resource_source, _cn_resource_cache
    _resource_cache = []
    _resource_source = ""
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
