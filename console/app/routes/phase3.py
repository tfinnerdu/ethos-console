"""Phase 3 stubs: UniData Field Diff and Colleague Direct Query.

Both features require a UniData/Colleague ODBC connection configured via
UNIDATA_CONN_STR.  Until that env var is set the endpoints return 503 with
a clear setup guide.  The UI scaffolds the full experience so the pages are
ready to wire up once the connection string is available.
"""
from flask import Blueprint, jsonify, request, current_app

phase3_bp = Blueprint("phase3", __name__)


def _require_unidata():
    conn = current_app.config.get("UNIDATA_CONN_STR", "")
    if not conn:
        return jsonify({
            "error": "UniData connection not configured",
            "setup": (
                "Set UNIDATA_CONN_STR in .env to enable this feature. "
                "Format: DSN=ColleagueDS;UID=svc-console;PWD=<password> "
                "Requires pyodbc and the UniData ODBC driver installed on the host."
            ),
        }), 503
    return None


# ── Field Diff ────────────────────────────────────────────────────────────────

@phase3_bp.get("/field-diff/<resource>")
def field_diff(resource: str):
    """Compare EEDM fields (from Ethos introspection) against UniData file fields."""
    err = _require_unidata()
    if err:
        return err

    from app import get_ethos
    ethos = get_ethos(current_app._get_current_object())
    if not ethos.is_configured():
        return jsonify({"error": "Ethos API key not configured"}), 503

    # Placeholder — real implementation queries UniData DICT via pyodbc
    return jsonify({
        "resource": resource,
        "eedm_fields": [],
        "unidata_fields": [],
        "matched": [],
        "eedm_only": [],
        "unidata_only": [],
        "note": "UniData ODBC query not yet implemented — connection is configured.",
    })


@phase3_bp.get("/unidata-files")
def list_unidata_files():
    """List available UniData files (VOC entries of type F/Q)."""
    err = _require_unidata()
    if err:
        return err
    return jsonify({"items": [], "note": "UniData file listing not yet implemented."})


# ── Colleague Direct Query ────────────────────────────────────────────────────

@phase3_bp.post("/colleague-query")
def run_colleague_query():
    """Execute a UniQuery or Envision SELECT against Colleague via ODBC."""
    err = _require_unidata()
    if err:
        return err

    data = request.get_json(force=True) or {}
    statement = data.get("statement", "").strip()
    if not statement:
        return jsonify({"error": "statement is required"}), 400

    # Placeholder — real implementation runs statement via pyodbc cursor
    return jsonify({
        "columns": [],
        "rows": [],
        "row_count": 0,
        "note": "Colleague ODBC query not yet implemented — connection is configured.",
    })


@phase3_bp.get("/colleague-files")
def list_colleague_files():
    """List Colleague file names available via ODBC."""
    err = _require_unidata()
    if err:
        return err
    return jsonify({"items": [], "note": "File listing not yet implemented."})
