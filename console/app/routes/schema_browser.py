"""EEDM Schema Browser + Validator.

/api/schema-browser/types          — list of all EEDM types from introspection
/api/schema-browser/type/<name>    — fields + descriptions for one type
/api/schema-browser/resource-schema/<resource>  — JSON Schema from Ethos API
/api/schema-browser/validate       — validate a payload against the fetched schema
"""
import jsonschema
import requests as req
import time
from flask import Blueprint, jsonify, request, current_app
from app import get_ethos
from app.request_utils import get_json_body
from app.routes.graphql_routes import _schema_cache, INTROSPECTION_QUERY, SCHEMA_CACHE_TTL

schema_browser_bp = Blueprint("schema_browser", __name__)


def _get_schema(ethos):
    """Return the cached (unwrapped) introspection schema, fetching if needed.

    Raises RuntimeError when introspection returns no usable __schema, so callers
    surface an honest error instead of a misleading 'type not found'. A cached
    available-resources fallback (written by the GraphQL tab) is ignored here —
    the Schema Browser needs a real introspection schema, not the fallback shape.
    """
    import app.routes.graphql_routes as gr
    cached = gr._schema_cache
    age = time.time() - gr._schema_cache_time
    if (
        cached is not None
        and age < SCHEMA_CACHE_TTL
        and cached.get("_source") != "available-resources"
    ):
        return cached
    result = ethos.graphql(INTROSPECTION_QUERY)
    schema = (result.get("data") or {}).get("__schema")
    if not schema:
        errors = result.get("errors") or []
        detail = (
            errors[0].get("message")
            if errors and isinstance(errors[0], dict)
            else "introspection returned no __schema"
        )
        raise RuntimeError(f"GraphQL introspection unavailable — {detail}")
    gr._schema_cache = schema
    gr._schema_cache_time = time.time()
    return schema


def _build_type_map(schema_data: dict) -> dict:
    types = schema_data.get("types", [])
    return {t["name"]: t for t in types}


@schema_browser_bp.get("/types")
def list_types():
    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured"}), 503
    try:
        schema = _get_schema(ethos)
        type_map = _build_type_map(schema)
        query_type_name = schema.get("queryType", {}).get("name", "Query")
        query_type = type_map.get(query_type_name, {})
        resources = []
        for field in (query_type.get("fields") or []):
            resources.append({
                "name": field["name"],
                "return_type": _resolve_type_name(field.get("type")),
            })
        resources.sort(key=lambda x: x["name"])
        return jsonify({"items": resources, "total": len(resources)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@schema_browser_bp.get("/type/<type_name>")
def get_type(type_name: str):
    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured"}), 503
    try:
        schema = _get_schema(ethos)
        type_map = _build_type_map(schema)
        t = type_map.get(type_name)
        if not t:
            # The Schema Browser type list shows Query *field* (resource) names.
            # A field name is not always also a type name, so when the direct
            # lookup misses, resolve the field to its return type and retry.
            query_type = type_map.get(
                schema.get("queryType", {}).get("name", "Query"), {}
            )
            for field in (query_type.get("fields") or []):
                if field.get("name") == type_name:
                    t = type_map.get(_resolve_type_name(field.get("type")))
                    break
        if not t:
            return jsonify({
                "error": f"Type '{type_name}' not found in the introspected schema"
            }), 404
        return jsonify({
            "name": t["name"],
            "kind": t.get("kind"),
            "fields": [
                {
                    "name": f["name"],
                    "type": _resolve_type_name(f.get("type")),
                    "nullable": _is_nullable(f.get("type")),
                }
                for f in (t.get("fields") or [])
            ],
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@schema_browser_bp.get("/resource-schema/<resource>")
def get_resource_schema(resource: str):
    """Fetch the JSON Schema for a resource version from Ethos."""
    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured"}), 503
    version = request.args.get("version")
    try:
        accept = (
            f"application/vnd.hedtech.integration.v{version}+json"
            if version
            else "application/json"
        )
        headers = ethos.get_headers(accept)
        headers["Accept"] = "application/schema+json"
        r = req.get(
            f"{ethos.base_url}/api/{resource}",
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@schema_browser_bp.post("/validate")
def validate_payload():
    """Validate a JSON payload against the EEDM JSON Schema for a resource."""
    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured"}), 503

    data = get_json_body(request)
    resource = data.get("resource", "").strip()
    version = data.get("version", "").strip()
    payload = data.get("payload")

    if not resource:
        return jsonify({"error": "resource is required"}), 400
    if payload is None:
        return jsonify({"error": "payload is required"}), 400

    try:
        headers = ethos.get_headers()
        headers["Accept"] = "application/schema+json"
        if version:
            headers["Accept"] = f"application/vnd.hedtech.integration.v{version}+json"
        r = req.get(f"{ethos.base_url}/api/{resource}", headers=headers, timeout=15)
        r.raise_for_status()
        schema = r.json()
    except Exception as exc:
        return jsonify({"error": f"Could not fetch schema: {exc}"}), 502

    errors = []
    try:
        validator = jsonschema.Draft7Validator(schema)
        for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
            errors.append({
                "path": "/".join(str(p) for p in err.path) or "(root)",
                "message": err.message,
                "schema_path": "/".join(str(p) for p in err.schema_path),
            })
    except jsonschema.SchemaError as exc:
        return jsonify({"error": f"Invalid schema: {exc.message}"}), 502

    return jsonify({
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors[:50],
    })


def _resolve_type_name(type_ref) -> str:
    if not type_ref:
        return "Unknown"
    if type_ref.get("name"):
        return type_ref["name"]
    return _resolve_type_name(type_ref.get("ofType"))


def _is_nullable(type_ref) -> bool:
    if not type_ref:
        return True
    return type_ref.get("kind") != "NON_NULL"
