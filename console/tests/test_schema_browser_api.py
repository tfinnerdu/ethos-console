"""Tests for /api/schema-browser endpoints.

The four routes covered:
  GET  /api/schema-browser/types                   — list_types
  GET  /api/schema-browser/type/<name>             — get_type
  GET  /api/schema-browser/resource-schema/<res>   — get_resource_schema
  POST /api/schema-browser/validate                — validate_payload
"""
import time
from unittest.mock import MagicMock, patch
import pytest


# ── Fixtures / helpers ────────────────────────────────────────────────────────

SAMPLE_SCHEMA = {
    "queryType": {"name": "Query"},
    "types": [
        {
            "name": "Query",
            "kind": "OBJECT",
            "fields": [
                {
                    "name": "persons16",
                    "type": {"kind": "OBJECT", "name": "Persons16Connection", "ofType": None},
                },
                {
                    "name": "courses16",
                    "type": {"kind": "OBJECT", "name": "Courses16Connection", "ofType": None},
                },
            ],
        },
        {
            "name": "PersonType",
            "kind": "OBJECT",
            "fields": [
                {
                    "name": "id",
                    "type": {
                        "kind": "NON_NULL",
                        "name": None,
                        "ofType": {"kind": "SCALAR", "name": "String", "ofType": None},
                    },
                },
                {
                    "name": "fullName",
                    "type": {"kind": "SCALAR", "name": "String", "ofType": None},
                },
            ],
        },
    ],
}


@pytest.fixture()
def sb_client(app, mock_ethos):
    """Test client with Ethos configured and schema cache pre-populated."""
    import app.routes.graphql_routes as gr
    orig_cache = gr._schema_cache
    orig_time = gr._schema_cache_time
    gr._schema_cache = SAMPLE_SCHEMA
    gr._schema_cache_time = time.time()  # fresh cache — won't refetch
    yield app.test_client()
    gr._schema_cache = orig_cache
    gr._schema_cache_time = orig_time


@pytest.fixture()
def unconfigured_client(app):
    """Test client where Ethos is NOT configured."""
    original = app.extensions.get("ethos_client")
    mock = MagicMock()
    mock.is_configured.return_value = False
    app.extensions["ethos_client"] = mock
    yield app.test_client()
    app.extensions["ethos_client"] = original


# ── list_types ────────────────────────────────────────────────────────────────

def test_list_types_200(sb_client):
    r = sb_client.get("/api/schema-browser/types")
    assert r.status_code == 200


def test_list_types_has_items_and_total(sb_client):
    data = sb_client.get("/api/schema-browser/types").get_json()
    assert "items" in data
    assert "total" in data


def test_list_types_returns_query_root_fields(sb_client):
    data = sb_client.get("/api/schema-browser/types").get_json()
    names = [item["name"] for item in data["items"]]
    assert "courses16" in names
    assert "persons16" in names


def test_list_types_sorted_alphabetically(sb_client):
    data = sb_client.get("/api/schema-browser/types").get_json()
    names = [item["name"] for item in data["items"]]
    assert names == sorted(names)


def test_list_types_item_has_return_type(sb_client):
    data = sb_client.get("/api/schema-browser/types").get_json()
    item = next(i for i in data["items"] if i["name"] == "persons16")
    assert item["return_type"] == "Persons16Connection"


def test_list_types_503_when_not_configured(unconfigured_client):
    r = unconfigured_client.get("/api/schema-browser/types")
    assert r.status_code == 503


def test_list_types_502_on_ethos_error(app, mock_ethos):
    import app.routes.graphql_routes as gr
    orig_cache = gr._schema_cache
    orig_time = gr._schema_cache_time
    gr._schema_cache = None
    gr._schema_cache_time = 0.0
    mock_ethos.graphql.side_effect = Exception("connection refused")
    try:
        r = app.test_client().get("/api/schema-browser/types")
        assert r.status_code == 502
    finally:
        mock_ethos.graphql.side_effect = None
        gr._schema_cache = orig_cache
        gr._schema_cache_time = orig_time


# ── get_type ──────────────────────────────────────────────────────────────────

def test_get_type_200_for_known_type(sb_client):
    r = sb_client.get("/api/schema-browser/type/PersonType")
    assert r.status_code == 200


def test_get_type_has_name_kind_fields(sb_client):
    data = sb_client.get("/api/schema-browser/type/PersonType").get_json()
    assert data["name"] == "PersonType"
    assert data["kind"] == "OBJECT"
    assert isinstance(data["fields"], list)


def test_get_type_field_shape(sb_client):
    data = sb_client.get("/api/schema-browser/type/PersonType").get_json()
    id_field = next(f for f in data["fields"] if f["name"] == "id")
    assert id_field["type"] == "String"
    assert id_field["nullable"] is False  # NON_NULL wrapper


def test_get_type_nullable_field(sb_client):
    data = sb_client.get("/api/schema-browser/type/PersonType").get_json()
    full_name = next(f for f in data["fields"] if f["name"] == "fullName")
    assert full_name["nullable"] is True


def test_get_type_404_for_unknown_type(sb_client):
    r = sb_client.get("/api/schema-browser/type/DoesNotExist")
    assert r.status_code == 404
    assert "not found" in r.get_json()["error"].lower()


def test_get_type_503_when_not_configured(unconfigured_client):
    r = unconfigured_client.get("/api/schema-browser/type/PersonType")
    assert r.status_code == 503


# The type list in the Schema Browser shows Query *field* (resource) names.
# A field name is not always also a type name, so get_type must resolve the
# field to its return type before giving up — otherwise every resource click
# returns a misleading "Type 'X' not found".
FIELD_RESOLUTION_SCHEMA = {
    "queryType": {"name": "Query"},
    "types": [
        {
            "name": "Query",
            "kind": "OBJECT",
            "fields": [
                {
                    "name": "advancementAppointments0",
                    "type": {"kind": "OBJECT", "name": "AdvancementAppointment", "ofType": None},
                },
            ],
        },
        {
            "name": "AdvancementAppointment",
            "kind": "OBJECT",
            "fields": [
                {"name": "id", "type": {"kind": "SCALAR", "name": "String", "ofType": None}},
            ],
        },
    ],
}


def test_get_type_resolves_query_field_name_to_return_type(app, mock_ethos):
    """A type-list entry is a Query field name; get_type resolves it to the type."""
    import app.routes.graphql_routes as gr
    orig_cache, orig_time = gr._schema_cache, gr._schema_cache_time
    gr._schema_cache = FIELD_RESOLUTION_SCHEMA
    gr._schema_cache_time = time.time()
    try:
        r = app.test_client().get("/api/schema-browser/type/advancementAppointments0")
        assert r.status_code == 200
        assert r.get_json()["name"] == "AdvancementAppointment"
    finally:
        gr._schema_cache, gr._schema_cache_time = orig_cache, orig_time


def test_get_type_502_when_introspection_returns_no_schema(app, mock_ethos):
    """Empty/failed introspection must surface an honest error, not 'type not found'."""
    import app.routes.graphql_routes as gr
    orig_cache, orig_time = gr._schema_cache, gr._schema_cache_time
    gr._schema_cache = None
    gr._schema_cache_time = 0.0
    mock_ethos.graphql.return_value = {"errors": [{"message": "introspection disabled"}]}
    try:
        r = app.test_client().get("/api/schema-browser/type/persons16")
        assert r.status_code == 502
        assert "introspection" in r.get_json()["error"].lower()
    finally:
        mock_ethos.graphql.return_value = {"data": {}}
        gr._schema_cache, gr._schema_cache_time = orig_cache, orig_time


# ── get_resource_schema ───────────────────────────────────────────────────────

SAMPLE_JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "names": {"type": "array"},
    },
    "required": ["id"],
}


def test_get_resource_schema_200(app, mock_ethos):
    mock_ethos.base_url = "https://integrate.elluciancloud.com"
    mock_ethos.get_headers.return_value = {"Authorization": "Bearer tok", "Accept": "application/json"}
    mock_resp = MagicMock()
    mock_resp.json.return_value = SAMPLE_JSON_SCHEMA
    mock_resp.raise_for_status = MagicMock()
    with patch("app.routes.schema_browser.req.get", return_value=mock_resp):
        r = app.test_client().get("/api/schema-browser/resource-schema/persons")
    assert r.status_code == 200
    assert r.get_json()["type"] == "object"


def test_get_resource_schema_correct_url(app, mock_ethos):
    mock_ethos.base_url = "https://integrate.elluciancloud.com"
    mock_ethos.get_headers.return_value = {"Authorization": "Bearer tok", "Accept": "application/json"}
    mock_resp = MagicMock()
    mock_resp.json.return_value = {}
    mock_resp.raise_for_status = MagicMock()
    with patch("app.routes.schema_browser.req.get", return_value=mock_resp) as mock_get:
        app.test_client().get("/api/schema-browser/resource-schema/persons")
    call_url = mock_get.call_args[0][0]
    assert call_url.endswith("/api/persons")


def test_get_resource_schema_503_when_not_configured(unconfigured_client):
    r = unconfigured_client.get("/api/schema-browser/resource-schema/persons")
    assert r.status_code == 503


def test_get_resource_schema_502_on_http_error(app, mock_ethos):
    mock_ethos.base_url = "https://integrate.elluciancloud.com"
    mock_ethos.get_headers.return_value = {"Authorization": "Bearer tok", "Accept": "application/json"}
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("HTTP 404")
    with patch("app.routes.schema_browser.req.get", return_value=mock_resp):
        r = app.test_client().get("/api/schema-browser/resource-schema/persons")
    assert r.status_code == 502


# ── validate_payload ──────────────────────────────────────────────────────────

def _make_validate_client(app, mock_ethos, schema=None):
    """Return a test client whose schema fetch returns `schema`."""
    mock_ethos.base_url = "https://integrate.elluciancloud.com"
    mock_ethos.get_headers.return_value = {"Authorization": "Bearer tok", "Accept": "application/json"}
    if schema is None:
        schema = SAMPLE_JSON_SCHEMA
    mock_resp = MagicMock()
    mock_resp.json.return_value = schema
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def test_validate_400_when_resource_missing(app, mock_ethos):
    r = app.test_client().post(
        "/api/schema-browser/validate",
        json={"payload": {"id": "abc"}},
    )
    assert r.status_code == 400
    assert "resource" in r.get_json()["error"]


def test_validate_400_when_payload_missing(app, mock_ethos):
    r = app.test_client().post(
        "/api/schema-browser/validate",
        json={"resource": "persons"},
    )
    assert r.status_code == 400
    assert "payload" in r.get_json()["error"]


def test_validate_503_when_not_configured(unconfigured_client):
    r = unconfigured_client.post(
        "/api/schema-browser/validate",
        json={"resource": "persons", "payload": {}},
    )
    assert r.status_code == 503


def test_validate_valid_payload(app, mock_ethos):
    mock_resp = _make_validate_client(app, mock_ethos)
    with patch("app.routes.schema_browser.req.get", return_value=mock_resp):
        r = app.test_client().post(
            "/api/schema-browser/validate",
            json={"resource": "persons", "payload": {"id": "abc"}},
        )
    assert r.status_code == 200
    data = r.get_json()
    assert data["valid"] is True
    assert data["error_count"] == 0
    assert data["errors"] == []


def test_validate_invalid_payload_returns_errors(app, mock_ethos):
    schema = {
        "type": "object",
        "properties": {"id": {"type": "integer"}},
        "required": ["id"],
    }
    mock_resp = _make_validate_client(app, mock_ethos, schema=schema)
    with patch("app.routes.schema_browser.req.get", return_value=mock_resp):
        r = app.test_client().post(
            "/api/schema-browser/validate",
            json={"resource": "persons", "payload": {"id": "not-an-int"}},
        )
    data = r.get_json()
    assert data["valid"] is False
    assert data["error_count"] >= 1
    assert len(data["errors"]) >= 1


def test_validate_error_shape(app, mock_ethos):
    schema = {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}}
    mock_resp = _make_validate_client(app, mock_ethos, schema=schema)
    with patch("app.routes.schema_browser.req.get", return_value=mock_resp):
        r = app.test_client().post(
            "/api/schema-browser/validate",
            json={"resource": "persons", "payload": {}},
        )
    errors = r.get_json()["errors"]
    assert len(errors) >= 1
    err = errors[0]
    assert "path" in err
    assert "message" in err
    assert "schema_path" in err


def test_validate_502_when_schema_fetch_fails(app, mock_ethos):
    mock_ethos.base_url = "https://integrate.elluciancloud.com"
    mock_ethos.get_headers.return_value = {"Authorization": "Bearer tok", "Accept": "application/json"}
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("network error")
    with patch("app.routes.schema_browser.req.get", return_value=mock_resp):
        r = app.test_client().post(
            "/api/schema-browser/validate",
            json={"resource": "persons", "payload": {"id": "abc"}},
        )
    assert r.status_code == 502
    assert "Could not fetch schema" in r.get_json()["error"]
