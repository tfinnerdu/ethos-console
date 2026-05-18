import csv
import io
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, current_app, Response
from sqlalchemy import text

from app.database import db, EthosErrorLog

errors_bp = Blueprint("errors", __name__)


def _apply_filters(query, args):
    source = args.get("source")
    resource_name = args.get("resource_name")
    http_status = args.get("http_status")
    from_ts = args.get("from_ts")
    to_ts = args.get("to_ts")

    if source:
        query = query.filter(EthosErrorLog.source == source)
    if resource_name:
        query = query.filter(EthosErrorLog.resource_name == resource_name)
    if http_status:
        try:
            query = query.filter(EthosErrorLog.http_status == int(http_status))
        except ValueError:
            pass
    if from_ts:
        try:
            query = query.filter(EthosErrorLog.timestamp >= datetime.fromisoformat(from_ts))
        except ValueError:
            pass
    if to_ts:
        try:
            query = query.filter(EthosErrorLog.timestamp <= datetime.fromisoformat(to_ts))
        except ValueError:
            pass
    return query


@errors_bp.get("/")
def list_errors():
    args = request.args
    # Accept limit/offset (JS convention) or page/per_page (SQLAlchemy convention)
    if "limit" in args or "offset" in args:
        limit = int(args.get("limit", 50))
        offset = int(args.get("offset", 0))
        per_page = limit
        page = (offset // limit) + 1 if limit else 1
    else:
        page = int(args.get("page", 1))
        per_page = int(args.get("per_page", 50))

    q = EthosErrorLog.query.order_by(EthosErrorLog.timestamp.desc())
    q = _apply_filters(q, args)

    paginated = q.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": [e.to_dict() for e in paginated.items],
        "total": paginated.total,
        "page": page,
        "per_page": per_page,
        "pages": paginated.pages,
    })


@errors_bp.get("/spikes")
def error_spikes():
    try:
        result = db.session.execute(
            text(
                "SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour, count(*) as count "
                "FROM ethos_error_log "
                "GROUP BY hour "
                "ORDER BY hour DESC "
                "LIMIT 48"
            )
        )
        rows = [{"hour": row[0], "count": row[1]} for row in result]
        return jsonify({"items": rows})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@errors_bp.get("/export")
def export_errors():
    q = EthosErrorLog.query.order_by(EthosErrorLog.timestamp.desc())
    q = _apply_filters(q, request.args)
    rows = q.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "source", "endpoint", "http_status", "error_message", "resource_name"])
    for e in rows:
        writer.writerow([
            e.id,
            e.timestamp.isoformat() if e.timestamp else "",
            e.source or "",
            e.endpoint or "",
            e.http_status or "",
            e.error_message or "",
            e.resource_name or "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=ethos_errors.csv"},
    )


@errors_bp.post("/")
def create_error():
    data = request.get_json(force=True) or {}
    entry = EthosErrorLog(
        source=data.get("source"),
        endpoint=data.get("endpoint"),
        http_status=data.get("http_status"),
        error_message=data.get("error_message"),
        resource_name=data.get("resource_name"),
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify(entry.to_dict()), 201


@errors_bp.post("/flush")
def flush_errors():
    hm = current_app.extensions.get("health_monitor")
    if hm is None:
        return jsonify({"error": "health_monitor not available"}), 503

    flushed = 0
    for err in list(getattr(hm, "error_log", [])):
        entry = EthosErrorLog(
            source=err.get("source", "health_monitor"),
            endpoint=err.get("endpoint"),
            http_status=err.get("http_status"),
            error_message=err.get("error_message") or err.get("message"),
            resource_name=err.get("resource_name"),
        )
        db.session.add(entry)
        flushed += 1

    db.session.commit()
    return jsonify({"flushed": flushed})
