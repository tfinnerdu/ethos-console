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
