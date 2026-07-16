"""Tests for /api/graphql-console endpoints."""
from unittest.mock import patch


INTROSPECTION_STUB = {
    "queryType": {"name": "Query"},
    "types": [
        {
            "name": "Query",
            "kind": "OBJECT",
            "fields": [
                {"name": "persons16", "type": {"kind": "OBJECT", "name": "Persons16Connection", "ofType": None}},
            ],
        },
        {
            "name": "Persons16Connection",
            "kind": "OBJECT",
            "fields": [
                {"name": "edges", "type": {"kind": "LIST", "name": None, "ofType": {"name": "Persons16Edge", "kind": "OBJECT"}}},
            ],
        },
        {
            "name": "Persons16Edge",
            "kind": "OBJECT",
            "fields": [
                {"name": "node", "type": {"kind": "OBJECT", "name": "Person16", "ofType": None}},
            ],
        },
        {
            "name": "Person16",
            "kind": "OBJECT",
            "fields": [
                {"name": "id", "type": {"kind": "SCALAR", "name": "ID", "ofType": None}},
                {"name": "fullName", "type": {"kind": "SCALAR", "name": "String", "ofType": None}},
            ],
        },
    ],
}


def test_schema_no_api_key(client):
    r = client.get("/api/graphql-console/schema")
    assert r.status_code == 503
    assert "error" in r.get_json()


def test_schema_with_mock_ethos(client, mock_ethos):
    mock_ethos.graphql.return_value = {"data": {"__schema": INTROSPECTION_STUB}}
    import app.routes.graphql_routes as gr
    gr._schema_cache = None  # clear module-level cache

    r = client.get("/api/graphql-console/schema")
    assert r.status_code == 200
    data = r.get_json()
    assert "queryType" in data
    assert "types" in data


def test_execute_no_api_key(client):
    r = client.post("/api/graphql-console/execute", json={"query": "{ persons16 { edges { node { id } } } }"})
    assert r.status_code == 503


def test_execute_success_emits_audit_event(client, mock_ethos, app):
    from app.database import AuditEntry
    mock_ethos.graphql.return_value = {"data": {"persons16": {"edges": []}}}
    query = "{ persons16 { edges { node { id } } } }"
    r = client.post("/api/graphql-console/execute", json={"query": query})
    assert r.status_code == 200
    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="call", resource_type="ethos_graphql", resource_id=query,
        ).first()
    assert entry is not None
    assert entry.outcome == "success"
    assert entry.detail == {"has_variables": False}


def test_execute_with_variables_flags_has_variables_without_storing_them(client, mock_ethos, app):
    from app.database import AuditEntry
    mock_ethos.graphql.return_value = {"data": {}}
    query = "mutation UpdateDob($id: ID!, $dob: String!) { x }"
    r = client.post("/api/graphql-console/execute", json={
        "query": query, "variables": {"id": "1001", "dob": "1980-01-01"},
    })
    assert r.status_code == 200
    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="call", resource_type="ethos_graphql", resource_id=query,
        ).first()
    assert entry is not None
    assert entry.detail == {"has_variables": True}
    # The actual variable values (a real DOB here) must never land in the audit row.
    assert "1980-01-01" not in str(entry.detail)


def test_execute_failure_emits_audit_event(client, mock_ethos, app):
    from app.database import AuditEntry
    mock_ethos.graphql.side_effect = RuntimeError("upstream rejected query")
    query = "{ broken"
    r = client.post("/api/graphql-console/execute", json={"query": query})
    assert r.status_code == 502
    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="call", resource_type="ethos_graphql", resource_id=query,
        ).first()
    assert entry is not None
    assert entry.outcome == "failure"
    assert "upstream rejected query" in entry.failure_reason


# ── /schema/raw ────────────────────────────────────────────────────────────────

def test_schema_raw_no_api_key(client):
    r = client.get("/api/graphql-console/schema/raw")
    assert r.status_code == 503


def test_schema_raw_returns_introspection_response(client, mock_ethos):
    mock_ethos.graphql.return_value = {"data": {"__schema": INTROSPECTION_STUB}}
    r = client.get("/api/graphql-console/schema/raw")
    assert r.status_code == 200
    assert r.get_json() == {"data": {"__schema": INTROSPECTION_STUB}}


def test_schema_raw_upstream_error_returns_502(client, mock_ethos):
    mock_ethos.graphql.side_effect = RuntimeError("timed out")
    r = client.get("/api/graphql-console/schema/raw")
    assert r.status_code == 502
    assert "timed out" in r.get_json()["error"]


# ── DELETE /schema (cache invalidation) ──────────────────────────────────────

def test_invalidate_schema_cache(client, mock_ethos):
    mock_ethos.graphql.return_value = {"data": {"__schema": INTROSPECTION_STUB}}
    import app.routes.graphql_routes as gr

    # Prime the cache with a GET, confirm it's set, then invalidate.
    client.get("/api/graphql-console/schema")
    assert gr._schema_cache is not None

    r = client.delete("/api/graphql-console/schema")
    assert r.status_code == 200
    assert r.get_json() == {"invalidated": True}
    assert gr._schema_cache is None
    assert gr._schema_cache_time == 0.0


def test_saved_queries_list(client):
    r = client.get("/api/graphql-console/saved")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_saved_queries_includes_preloaded(client):
    data = client.get("/api/graphql-console/saved").get_json()
    preloaded = [q for q in data["items"] if q.get("is_preloaded")]
    assert len(preloaded) > 0


def test_save_and_delete_query(client):
    payload = {
        "name": "Test Query",
        "description": "pytest",
        "query_text": "query { persons16 { edges { node { id } } } }",
        "variables": {},
    }
    r = client.post("/api/graphql-console/saved", json=payload)
    assert r.status_code == 201
    qid = r.get_json()["id"]

    r = client.delete(f"/api/graphql-console/saved/{qid}")
    assert r.status_code == 200


def test_cannot_delete_preloaded(client):
    data = client.get("/api/graphql-console/saved").get_json()
    preloaded_id = next(q["id"] for q in data["items"] if q.get("is_preloaded"))
    r = client.delete(f"/api/graphql-console/saved/{preloaded_id}")
    assert r.status_code == 403


def test_save_and_delete_query_emit_audit_events(client, app):
    from app.database import AuditEntry
    payload = {
        "name": "Audited Query",
        "description": "pytest",
        "query_text": "query { persons16 { edges { node { id } } } }",
        "variables": {},
    }
    r = client.post("/api/graphql-console/saved", json=payload)
    qid = r.get_json()["id"]
    client.delete(f"/api/graphql-console/saved/{qid}")

    with app.app_context():
        actions = {
            e.action for e in AuditEntry.query.filter_by(resource_id=str(qid)).all()
        }
    assert {"create", "delete"} <= actions
