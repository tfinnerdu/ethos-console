"""Phase 3: UniData Field Diff and Colleague Direct Query via uopy."""
from flask import Blueprint, jsonify, request, current_app

try:
    import uopy as _uopy
    _UOPY_AVAILABLE = True
except ImportError:
    _UOPY_AVAILABLE = False

phase3_bp = Blueprint("phase3", __name__)

_PARSE_SKIP = {"LIST", "VOC", "records listed", "@ID", "....."}


def _is_configured() -> bool:
    return bool(
        current_app.config.get("UNIDATA_HOST")
        and current_app.config.get("UNIDATA_ACCOUNT")
    )


def _require_unidata():
    if not _UOPY_AVAILABLE:
        return jsonify({
            "error": "uopy not installed",
            "setup": "Add uopy to requirements.txt and reinstall.",
        }), 503
    if not _is_configured():
        return jsonify({
            "error": "UniData connection not configured",
            "setup": (
                "Set UNIDATA_HOST, UNIDATA_USER, UNIDATA_PASSWORD, and "
                "UNIDATA_ACCOUNT in .env to enable this feature."
            ),
        }), 503
    return None


def _connect():
    return _uopy.connect(
        host=current_app.config["UNIDATA_HOST"],
        port=current_app.config.get("UNIDATA_PORT", 31438),
        user=current_app.config.get("UNIDATA_USER", ""),
        password=current_app.config.get("UNIDATA_PASSWORD", ""),
        account=current_app.config["UNIDATA_ACCOUNT"],
    )


def _parse_list_ids(response: str) -> list[str]:
    ids = []
    for line in response.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(skip in line for skip in _PARSE_SKIP):
            continue
        ids.append(line)
    return ids


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
        with _connect() as conn:  # noqa: F841
            cmd = _uopy.Command("LIST VOC WITH F1 = 'F' BY @ID")
            cmd.run()
            items = _parse_list_ids(cmd.response)
        return jsonify({"items": items})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Colleague Direct Query ────────────────────────────────────────────────────

@phase3_bp.post("/colleague-query")
def run_colleague_query():
    err = _require_unidata()
    if err:
        return err

    data = request.get_json(force=True) or {}
    statement = data.get("statement", "").strip()
    if not statement:
        return jsonify({"error": "statement is required"}), 400

    try:
        with _connect() as conn:  # noqa: F841
            cmd = _uopy.Command(statement)
            cmd.run()
            output = cmd.response
        return jsonify({"output": output})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@phase3_bp.get("/colleague-files")
def list_colleague_files():
    err = _require_unidata()
    if err:
        return err

    try:
        with _connect() as conn:  # noqa: F841
            cmd = _uopy.Command("LIST VOC WITH F1 = 'F' BY @ID")
            cmd.run()
            items = _parse_list_ids(cmd.response)
        return jsonify({"items": items})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
