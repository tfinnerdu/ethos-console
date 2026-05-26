from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, current_app
from app import get_ethos
from app.database import db, ResourceAnnotation

resources_bp = Blueprint("resources", __name__)

_resource_cache: list = []
_resource_source: str = ""  # "available-resources" or "graphql-schema"
_cn_resource_cache: list = []


def _populate_resource_cache(ethos) -> tuple[list, str, str | None]:
    """Resolve the resource list, falling back to GraphQL introspection when
    /api/available-resources is unreachable (401/404/scope issues on the
    tenant's application key).

    Returns (items, source, fallback_note). source is "available-resources"
    or "graphql-schema"; fallback_note is non-empty only when the fallback
    fired.
    """
    try:
        items = ethos.get_available_resources()
        return items, "available-resources", None
    except Exception as rest_exc:
        # The REST endpoint is meta-scoped on the application; some tenants'
        # application keys aren't authorized for it. GraphQL introspection
        # exposes the same resource list (query field names → camelCase,
        # trailing digits → version), so derive from there.
        #
        # Reuse the introspection cache shared with the Schema Browser and
        # GraphQL tab so we don't re-fetch the schema if it's already loaded.
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
            try:
                result = ethos.graphql(INTROSPECTION_QUERY)
            except Exception as gql_exc:
                raise RuntimeError(
                    f"REST /api/available-resources failed ({rest_exc}); "
                    f"GraphQL fallback also failed ({gql_exc})."
                ) from rest_exc
            schema = (result.get("data") or {}).get("__schema")
            if schema:
                # Populate the shared cache so the next Schema Browser /
                # GraphQL-tab visit doesn't refetch either.
                gr._schema_cache = schema
                gr._schema_cache_time = _time.time()

        if not schema:
            raise RuntimeError(
                f"REST /api/available-resources failed ({rest_exc}); "
                f"GraphQL fallback returned no schema."
            ) from rest_exc

        items = _resources_from_graphql_schema(schema)
        note = (
            f"Derived from GraphQL introspection — /api/available-resources "
            f"returned: {rest_exc}"
        )
        return items, "graphql-schema", note


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
