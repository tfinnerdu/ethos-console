"""Phase 3: UniData Field Diff and Colleague Direct Query via uopy."""
from flask import Blueprint, jsonify, request, current_app
from app.audit import Action, Outcome, write_event
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

    # This runs an arbitrary TCL/UniQuery statement directly against
    # Colleague with no further restriction beyond login — that's the
    # feature. The audit trail is the accountability for it: who ran what,
    # even though the statement text itself isn't secret the way applicant
    # PII is.
    try:
        output = _get_unidata().run_command(statement)
        write_event(Action.CALL, "unidata_command", statement[:500])
        return jsonify({"output": output})
    except Exception as exc:
        write_event(
            Action.CALL, "unidata_command", statement[:500],
            outcome=Outcome.FAILURE, failure_reason=str(exc),
        )
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

    # arg values often carry live Colleague record data (e.g. a person id or
    # name passed to CALC.PERSON) - log the subroutine name and arg count
    # only, not the argument values themselves, matching the PII-minimal
    # discipline used elsewhere in the audit trail.
    try:
        result = _get_unidata().call_subroutine(sub_name, args)
        write_event(Action.CALL, "unidata_subroutine", sub_name, detail={"arg_count": len(args)})
        return jsonify(result)
    except Exception as exc:
        write_event(
            Action.CALL, "unidata_subroutine", sub_name,
            outcome=Outcome.FAILURE, failure_reason=str(exc),
            detail={"arg_count": len(args)},
        )
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
