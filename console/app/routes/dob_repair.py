"""DOB Repair routes — /api/dob-repair/*

Review console for PD0002124 (Colleague Self-Service Instant Enrollment
stores DOB one day early for registrants whose browser timezone is east of
the Central-time server). Runs the detector (app/dob_detector.py) against a
PERSON export, surfaces a human-gated review queue, and exports approved
corrections as CSV.

This blueprint never writes to Colleague, Ethos, or NAE. It only persists
the reviewer's decision (accept/reject/defer) in this app's own database and
exports an approved-corrections CSV for a separate, sanctioned apply step
outside this tool.

Analysis state (the last-computed candidate list) is held in a
module-level, in-memory dict — recomputed on each /analyze call. Reviewer
decisions, unlike the analysis itself, are durable (see the DobDecision
model in app/database.py) and are re-joined against whatever candidate list
is currently in memory.
"""
import csv
import io
from datetime import datetime, timezone, date

from flask import Blueprint, Response, current_app, jsonify, request

from app.audit import Action, write_event
from app.database import db, DobDecision
from app import dob_detector as detector
from app import dob_sql_source

dob_repair_bp = Blueprint("dob_repair", __name__)

VALID_DECISIONS = {"accept", "reject", "defer"}

_STATE = {
    "result": None,        # detector.AnalysisResult
    "by_id": {},            # candidate_id -> detector.Candidate
    "source": None,
    "analyzed_at": None,
    "identity_threshold": detector.IDENTITY_THRESHOLD,
}


def _configured_input_path() -> str:
    return current_app.config.get("DOB_RECONCILE_INPUT_CSV", "").strip()


def _extra_ie_origin_values() -> set:
    raw = current_app.config.get("DOB_RECONCILE_IE_ORIGIN_CODES", "")
    return {v.strip() for v in raw.split(",") if v.strip()}


def _store_result(result, source: str, identity_threshold: int) -> None:
    _STATE["result"] = result
    _STATE["by_id"] = {c.candidate_id: c for c in result.candidates}
    _STATE["source"] = source
    _STATE["analyzed_at"] = datetime.now(timezone.utc).isoformat()
    _STATE["identity_threshold"] = identity_threshold


@dob_repair_bp.post("/analyze")
def analyze():
    """Run the detector against an uploaded CSV, or the configured path.

    Multipart form: csv_file (optional), threshold (optional, default 6).
    If csv_file is omitted, falls back to DOB_RECONCILE_INPUT_CSV.
    """
    try:
        threshold = int(request.form.get("threshold", detector.IDENTITY_THRESHOLD))
    except ValueError:
        return jsonify({"error": "threshold must be an integer"}), 400

    upload = request.files.get("csv_file")
    try:
        if upload and upload.filename:
            text = upload.stream.read().decode("utf-8-sig")
            records = detector.load_records(io.StringIO(text))
            source = upload.filename
        else:
            configured_path = _configured_input_path()
            if not configured_path:
                return jsonify({
                    "error": "No csv_file uploaded and DOB_RECONCILE_INPUT_CSV is not configured",
                    "setup": "Upload a csv_file, or set DOB_RECONCILE_INPUT_CSV in .env",
                }), 400
            records = detector.load_records(configured_path)
            source = configured_path
    except FileNotFoundError:
        return jsonify({
            "error": f"Configured input path not found: {_configured_input_path()}",
        }), 404
    except Exception as exc:
        current_app.logger.error("dob_repair analyze parse error: %s", exc, exc_info=True)
        return jsonify({"error": f"Could not parse CSV: {exc}"}), 400

    result = detector.analyze(records, identity_threshold=threshold, extra_ie_origin_values=_extra_ie_origin_values())
    _store_result(result, source, threshold)

    current_app.logger.info("dob_repair analyze: source=%s %s", source, result.summary)
    return jsonify({
        "source": source,
        "analyzed_at": _STATE["analyzed_at"],
        "identity_threshold": threshold,
        "summary": result.summary,
    })


@dob_repair_bp.post("/analyze/sql")
def analyze_sql():
    """Run the detector against DOB_RECONCILE_SQL_FILE, fetched live via SQL Server.

    Body (optional JSON): {threshold}. The query itself is not accepted here —
    it is drafted and owned by whoever configures DOB_RECONCILE_SQL_FILE on
    the server; this endpoint only runs whatever is currently in that file.
    """
    body = request.get_json(silent=True) or {}
    try:
        threshold = int(body.get("threshold", detector.IDENTITY_THRESHOLD))
    except (TypeError, ValueError):
        return jsonify({"error": "threshold must be an integer"}), 400

    if not dob_sql_source.is_configured():
        return jsonify({
            "error": "SQL fetch is not configured",
            "setup": "Set DOB_RECONCILE_SQL_FILE and DOB_RECONCILE_DB in .env",
        }), 503

    try:
        records = dob_sql_source.fetch_records()
    except ValueError as exc:
        # Read-only guard rejected the configured query, or it's empty.
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc), "setup": "Install pyodbc and the system ODBC driver"}), 503
    except Exception as exc:
        current_app.logger.error("dob_repair analyze_sql error: %s", exc, exc_info=True)
        return jsonify({"error": f"SQL fetch failed: {exc}"}), 502

    source = f"sql:{dob_sql_source.sql_file_path()}"
    result = detector.analyze(records, identity_threshold=threshold, extra_ie_origin_values=_extra_ie_origin_values())
    _store_result(result, source, threshold)

    current_app.logger.info(
        "dob_repair analyze via SQL: rows=%d %s", len(records), result.summary
    )
    return jsonify({
        "source": source,
        "analyzed_at": _STATE["analyzed_at"],
        "identity_threshold": threshold,
        "summary": result.summary,
    })


@dob_repair_bp.get("/status")
def status():
    """Whether an analysis has run, and which server-side input sources are configured."""
    result = _STATE["result"]
    return jsonify({
        "analyzed": result is not None,
        "analyzed_at": _STATE["analyzed_at"],
        "source": _STATE["source"],
        "identity_threshold": _STATE["identity_threshold"],
        "summary": result.summary if result else None,
        "configured_input_path": bool(_configured_input_path()),
        "sql_configured": dob_sql_source.is_configured(),
    })


def _decisions_by_candidate() -> dict:
    return {d.candidate_id: d.to_dict() for d in DobDecision.query.all()}


@dob_repair_bp.get("/candidates")
def list_candidates():
    """Candidate queue, elevated-risk worklist, and unparseable DOBs from the
    most recent analysis, each candidate joined with its reviewer decision
    (if any)."""
    result = _STATE["result"]
    if result is None:
        return jsonify({"error": "No analysis has been run yet"}), 404

    try:
        decisions = _decisions_by_candidate()
        candidates = []
        for c in result.candidates:
            row = c.as_row()
            row["decision"] = decisions.get(c.candidate_id)
            candidates.append(row)

        elevated = [
            {
                "person_id": r.person_id,
                "name": f"{r.first_name} {r.last_name}".strip(),
                "dob": r.birth_date.isoformat() if r.birth_date else "",
                "state": r.state,
            }
            for r in result.elevated_risk
        ]
        unparseable = [
            {
                "person_id": r.person_id,
                "name": f"{r.first_name} {r.last_name}".strip(),
                "raw_birth_date": r.raw_birth_date,
            }
            for r in result.unparseable_dob
        ]

        return jsonify({
            "summary": result.summary,
            "candidates": candidates,
            "elevated_risk": elevated,
            "unparseable_dob": unparseable,
        })
    except Exception as exc:
        current_app.logger.error("dob_repair list_candidates error: %s", exc, exc_info=True)
        return jsonify({"error": str(exc)}), 500


@dob_repair_bp.post("/decision")
def record_decision():
    """Record a reviewer decision for one candidate pair.

    Body: {candidate_id, action, true_dob?, reviewer?, note?}
    For action="accept", true_dob must match one side of the pair — the
    reviewer is asserting which date is correct; the OTHER record is the one
    flagged as needing correction.
    """
    body = request.get_json(silent=True) or {}
    candidate_id = (body.get("candidate_id") or "").strip()
    action = (body.get("action") or "").strip().lower()
    true_dob_raw = (body.get("true_dob") or "").strip()
    reviewer = (body.get("reviewer") or "unknown").strip()
    note = (body.get("note") or "").strip()

    cand = _STATE["by_id"].get(candidate_id)
    if cand is None:
        return jsonify({"error": "Unknown candidate_id — run /analyze first"}), 404
    if action not in VALID_DECISIONS:
        return jsonify({"error": f"action must be one of {sorted(VALID_DECISIONS)}"}), 400

    corrected_person_id = corrected_from = corrected_to = None
    if action == "accept":
        chosen = detector.parse_date(true_dob_raw)
        if chosen is None:
            return jsonify({
                "error": "accept requires a valid true_dob matching one side of the pair",
            }), 400
        earlier, later = cand.record_a, cand.record_b
        if chosen == later.birth_date:
            corrected_person_id = earlier.person_id
            corrected_from = _iso(earlier.birth_date)
            corrected_to = _iso(later.birth_date)
        elif chosen == earlier.birth_date:
            corrected_person_id = later.person_id
            corrected_from = _iso(later.birth_date)
            corrected_to = _iso(earlier.birth_date)
        else:
            return jsonify({
                "error": "true_dob must match either the earlier or later record's DOB",
            }), 400

    try:
        existing = db.session.get(DobDecision, candidate_id)
        if existing is None:
            existing = DobDecision(candidate_id=candidate_id)
            db.session.add(existing)
        existing.action = action
        existing.corrected_person_id = corrected_person_id
        existing.corrected_from = corrected_from
        existing.corrected_to = corrected_to
        existing.reviewer = reviewer
        existing.decided_at = datetime.now(timezone.utc)
        existing.note = note
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error("dob_repair record_decision error: %s", exc, exc_info=True)
        return jsonify({"error": str(exc)}), 500

    # Detail is deliberately minimal — candidate_id/action/reviewer only, no
    # DOB values or names — the DobDecision row (not this audit entry) is the
    # PII-bearing record of what changed.
    write_event(
        Action.UPDATE, "dob_decision", candidate_id,
        detail={"decision_action": action, "reviewer": reviewer},
    )

    current_app.logger.info(
        "dob_repair decision: candidate=%s action=%s corrected=%s reviewer=%s",
        candidate_id, action, corrected_person_id, reviewer,
    )
    return jsonify({
        "candidate_id": candidate_id,
        "action": action,
        "corrected_person_id": corrected_person_id,
        "corrected_from": corrected_from,
        "corrected_to": corrected_to,
    })


@dob_repair_bp.get("/export/corrections")
def export_corrections():
    """CSV of approved corrections for a sanctioned apply step OUTSIDE this
    tool. This is the only output that should touch a write path, and only
    through a reviewed, audited channel (Ethos PUT or manual NAE correction)."""
    try:
        accepted = (
            DobDecision.query.filter(
                DobDecision.action == "accept",
                DobDecision.corrected_person_id.isnot(None),
            )
            .order_by(DobDecision.decided_at)
            .all()
        )

        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "person_id", "current_dob", "corrected_dob",
                "decided_by", "decided_at", "candidate_id", "note",
            ],
        )
        writer.writeheader()
        for d in accepted:
            writer.writerow({
                "person_id": d.corrected_person_id,
                "current_dob": d.corrected_from,
                "corrected_dob": d.corrected_to,
                "decided_by": d.reviewer,
                "decided_at": d.decided_at.isoformat() if d.decided_at else "",
                "candidate_id": d.candidate_id,
                "note": d.note or "",
            })

        return Response(
            buf.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=dob_corrections.csv"},
        )
    except Exception as exc:
        current_app.logger.error("dob_repair export_corrections error: %s", exc, exc_info=True)
        return jsonify({"error": str(exc)}), 500


def _iso(d) -> str:
    return d.isoformat() if isinstance(d, date) else ""
