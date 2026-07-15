"""Phase 3: UniData Field Diff and Colleague Direct Query via uopy."""
from flask import Blueprint, jsonify, request, current_app
from app.request_utils import get_json_body

phase3_bp = Blueprint("phase3", __name__)


def _get_unidata():
    return current_app.extensions["unidata_client"]


def _require_unidata():
    unidata = _get_unidata()
    if not unidata.is_configured():
        return jsonify({
            "error": "UniData connection not configured",
            "setup": (
                "Set UNIDATA_HOST, UNIDATA_USER, UNIDATA_PASSWORD, and "
                "UNIDATA_ACCOUNT in .env to enable this feature (and ensure "
                "uopy is installed)."
            ),
        }), 503
    return None


# ── Field Diff ────────────────────────────────────────────────────────────────

@phase3_bp.get("/field-diff/<resource>")
def field_diff(resource: str):
    err = _require_unidata()
    if err:
        return err

    from app import get_ethos
    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured"}), 503

    return jsonify({
        "resource": resource,
        "eedm_fields": [],
        "unidata_fields": [],
        "matched": [],
        "eedm_only": [],
        "unidata_only": [],
        "note": "Field diff not yet implemented.",
    })


@phase3_bp.get("/unidata-files")
def list_unidata_files():
    err = _require_unidata()
    if err:
        return err
    try:
        return jsonify({"items": _get_unidata().list_files()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Colleague Direct Query ────────────────────────────────────────────────────

@phase3_bp.post("/colleague-query")
def run_colleague_query():
    err = _require_unidata()
    if err:
        return err

    data = get_json_body(request)
    statement = data.get("statement", "").strip()
    if not statement:
        return jsonify({"error": "statement is required"}), 400

    try:
        return jsonify({"output": _get_unidata().run_command(statement)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@phase3_bp.post("/subroutine")
def call_subroutine():
    err = _require_unidata()
    if err:
        return err

    data = get_json_body(request)
    sub_name = (data.get("name") or "").strip().upper()
    args = data.get("args") or []

    if not sub_name:
        return jsonify({"error": "name is required"}), 400

    try:
        return jsonify(_get_unidata().call_subroutine(sub_name, args))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@phase3_bp.get("/colleague-files")
def list_colleague_files():
    err = _require_unidata()
    if err:
        return err
    try:
        return jsonify({"items": _get_unidata().list_files()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
