"""Audit log helpers — one shared seam for every state-changing operation.

Per the project's Audit Emission Discipline standard:
  - one event per logical operation (not per fan-out item)
  - never emit from health endpoints
  - actor falls back to "system" outside a request context
  - correlation_id is auto-generated when not passed in
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from flask import g, has_request_context, request

from app.database import db, AuditEntry


# Canonical action verbs. Use these strings instead of free text so the audit
# log is queryable by action class.
class Action:
    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    PUBLISH = "publish"           # caustic — Ethos bus, downstream fan-out
    TRIGGER = "trigger"           # caustic — Conductor workflow run
    CALL = "call"                 # caustic — Colleague CTX / subroutine
    FLUSH = "flush"               # in-memory → persistent
    SWITCH = "switch"             # Ethos environment / runtime mode


# Canonical outcomes.
class Outcome:
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


def _resolve_actor() -> tuple[str, str | None]:
    """Return (actor_id, display_name) from the current request or fall back."""
    if has_request_context():
        actor = (
            g.get("current_user")
            or request.headers.get("X-Console-User")
            or "anonymous"
        )
        display = g.get("current_user_display") or None
        return str(actor), display
    return "system", None


def write_event(
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    outcome: str = Outcome.SUCCESS,
    *,
    failure_reason: str | None = None,
    detail: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditEntry:
    """Persist an audit row. Returns the saved row (id populated).

    Never raises on persistence errors — the caller's primary action must
    not fail because the audit write failed. Errors are swallowed and the
    return is None in that case.
    """
    actor, display = _resolve_actor()
    entry = AuditEntry(
        occurred_at=datetime.now(timezone.utc),
        actor=actor,
        actor_display_name=display,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        failure_reason=failure_reason,
        detail=detail,
        correlation_id=correlation_id or str(uuid.uuid4()),
    )
    try:
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None  # type: ignore[return-value]
    return entry


def query_events(
    page: int = 1,
    page_size: int = 50,
    *,
    actor: str | None = None,
    resource_id: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
) -> dict:
    """Paginated query over the audit log. Returns the same shape the CN tab
    has been consuming via the C# CNM endpoint, so the frontend is unchanged.
    """
    q = AuditEntry.query
    if actor:
        q = q.filter(AuditEntry.actor.ilike(f"%{actor}%"))
    if resource_id:
        q = q.filter(AuditEntry.resource_id.ilike(f"%{resource_id}%"))
    if action:
        q = q.filter(AuditEntry.action == action)
    if outcome:
        q = q.filter(AuditEntry.outcome == outcome)

    paged = q.order_by(AuditEntry.occurred_at.desc()).paginate(
        page=max(page, 1), per_page=max(page_size, 1), error_out=False
    )
    return {
        "items": [e.to_dict() for e in paged.items],
        "page": page,
        "pageSize": page_size,
        "totalPages": paged.pages,
        "totalCount": paged.total,
    }
