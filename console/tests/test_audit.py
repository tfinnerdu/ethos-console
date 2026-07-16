"""Tests for the audit log helper."""
import pytest

from app.audit import Action, Outcome, write_event, query_events
from app.database import AuditEntry


@pytest.fixture(autouse=True)
def clean_audit_table(app):
    """Each test starts with an empty audit log."""
    with app.app_context():
        AuditEntry.query.delete()
        from app.database import db as _db
        _db.session.commit()
    yield


def test_write_event_persists_row(app):
    with app.app_context():
        entry = write_event(Action.PUBLISH, "ethos.change_notification", "guid-1")
        assert entry is not None
        assert entry.id is not None
        assert entry.action == Action.PUBLISH
        assert entry.resource_type == "ethos.change_notification"
        assert entry.resource_id == "guid-1"
        assert entry.outcome == Outcome.SUCCESS
        assert entry.correlation_id  # auto-generated


def test_write_event_failure_outcome(app):
    with app.app_context():
        entry = write_event(
            Action.TRIGGER,
            "conductor.workflow",
            "EDA_Person_Sync",
            outcome=Outcome.FAILURE,
            failure_reason="503 Server Error",
        )
        assert entry.outcome == Outcome.FAILURE
        assert entry.failure_reason == "503 Server Error"


def test_write_event_detail_blob(app):
    with app.app_context():
        entry = write_event(
            Action.CALL, "colleague.transaction", "GET.PERSON.INFO",
            detail={"input_keys": ["KEY.PERSON"], "rows": 3},
        )
        assert entry.detail == {"input_keys": ["KEY.PERSON"], "rows": 3}


def test_write_event_actor_falls_back_to_system_outside_request(app):
    with app.app_context():
        entry = write_event(Action.VIEW, "console.health")
        assert entry.actor == "system"


def test_write_event_actor_uses_g_current_user_when_set(app):
    # app/auth.py's gate sets g.current_user from the session (local
    # username, or a real Entra identity) on every authenticated request —
    # this is what gives audit entries real per-user attribution instead of
    # falling back to "anonymous".
    from flask import g
    with app.test_request_context():
        g.current_user = "person@doane.edu"
        entry = write_event(Action.VIEW, "console.health")
    assert entry.actor == "person@doane.edu"


def test_write_event_actor_falls_back_to_anonymous_in_request_with_no_user(app):
    from flask import g
    with app.test_request_context():
        # g is scoped to the app context, which test_request_context() can
        # reuse rather than always creating fresh — clear defensively so
        # this test doesn't depend on running before/after any other test
        # that sets g.current_user on this same shared `app` fixture.
        g.pop("current_user", None)
        entry = write_event(Action.VIEW, "console.health")
    assert entry.actor == "anonymous"


def test_query_events_pagination_shape(app):
    with app.app_context():
        for i in range(5):
            write_event(Action.VIEW, "test", f"id-{i}")
        result = query_events(page=1, page_size=3)
        assert {"items", "page", "pageSize", "totalPages", "totalCount"} == set(result.keys())
        assert len(result["items"]) == 3
        assert result["totalCount"] == 5
        assert result["totalPages"] == 2


def test_query_events_ordered_newest_first(app):
    import time
    with app.app_context():
        write_event(Action.VIEW, "test", "old")
        time.sleep(0.01)
        write_event(Action.VIEW, "test", "new")
        result = query_events()
        assert result["items"][0]["resource_id"] == "new"
        assert result["items"][1]["resource_id"] == "old"


def test_query_events_filter_by_action(app):
    with app.app_context():
        write_event(Action.VIEW, "test", "a")
        write_event(Action.PUBLISH, "test", "b")
        write_event(Action.PUBLISH, "test", "c")
        result = query_events(action=Action.PUBLISH)
        assert result["totalCount"] == 2
        assert {i["resource_id"] for i in result["items"]} == {"b", "c"}


def test_query_events_filter_by_resource_id_substring(app):
    with app.app_context():
        write_event(Action.VIEW, "test", "persons-1")
        write_event(Action.VIEW, "test", "courses-1")
        result = query_events(resource_id="persons")
        assert result["totalCount"] == 1
        assert result["items"][0]["resource_id"] == "persons-1"
