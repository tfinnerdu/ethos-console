"""Tests for /api/resources endpoints."""
import pytest


@pytest.fixture(autouse=True)
def _reset_resource_cache(client):
    """Clear the module-level resource cache AND the shared introspection
    cache before each test so source / fallback / cache-reuse assertions
    aren't poisoned by another test file warming the schema cache."""
    import app.routes.graphql_routes as gr
    client.post("/api/resources/refresh")
    gr._schema_cache = None
    gr._schema_cache_time = 0.0
    yield
    client.post("/api/resources/refresh")
    gr._schema_cache = None
    gr._schema_cache_time = 0.0


def test_resources_list(client, mock_ethos):
    r = client.get("/api/resources/")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data


def test_resources_list_uses_rest_source_by_default(client, mock_ethos):
    """When /api/available-resources succeeds, the response source is the
    REST endpoint and no fallback note is attached."""
    data = client.get("/api/resources/").get_json()
    assert data["source"] == "available-resources"
    assert "note" not in data


def test_resources_list_falls_back_to_graphql_when_rest_fails(client, mock_ethos):
    """When /api/available-resources raises (401/404/scope issues), the
    route derives the list from GraphQL introspection so the tab still works."""
    mock_ethos.get_available_resources.side_effect = Exception(
        "401 Client Error: Unauthorized"
    )
    mock_ethos.graphql.return_value = {
        "data": {
            "__schema": {
                "queryType": {"name": "Query"},
                "types": [
                    {
                        "name": "Query",
                        "kind": "OBJECT",
                        "fields": [
                            {"name": "persons16", "type": {"name": "P16", "kind": "OBJECT"}},
                            {"name": "personAddresses11", "type": {"name": "PA11", "kind": "OBJECT"}},
                            {"name": "sections16", "type": {"name": "S16", "kind": "OBJECT"}},
                        ],
                    },
                ],
            }
        }
    }
    data = client.get("/api/resources/").get_json()
    assert data["source"] == "graphql-schema"
    assert "note" in data and "Derived from GraphQL" in data["note"]
    names = {i["name"] for i in data["items"]}
    assert {"persons", "person-addresses", "sections"} <= names
    persons = next(i for i in data["items"] if i["name"] == "persons")
    assert persons["latestVersion"] == "16"


def test_resources_fallback_reuses_shared_graphql_schema_cache(client, mock_ethos):
    """When the GraphQL fallback fires and the schema cache is already warm
    (Schema Browser / GraphQL tab loaded it), the resources route must
    reuse it instead of calling ethos.graphql() again."""
    import time
    import app.routes.graphql_routes as gr

    # Warm the shared cache as if Schema Browser had loaded it.
    gr._schema_cache = {
        "queryType": {"name": "Query"},
        "types": [{
            "name": "Query", "kind": "OBJECT",
            "fields": [{"name": "persons16", "type": {"name": "P", "kind": "OBJECT"}}],
        }],
    }
    gr._schema_cache_time = time.time()
    try:
        mock_ethos.get_available_resources.side_effect = Exception("401 Unauthorized")
        mock_ethos.graphql.reset_mock()
        data = client.get("/api/resources/").get_json()
        assert data["source"] == "graphql-schema"
        # The whole point: no fresh GraphQL call when the cache is warm.
        mock_ethos.graphql.assert_not_called()
    finally:
        gr._schema_cache = None
        gr._schema_cache_time = 0.0


def test_env_switch_clears_resource_cache(client, mock_ethos, app):
    """Switching environments must drop the resource cache so the next
    /api/resources/ call refetches against the new env's schema."""
    app.config["ETHOS_ENVIRONMENTS"] = [
        {"name": "Dev",  "url": "https://d.example", "key": "dk", "graphql_key": ""},
        {"name": "Test", "url": "https://t.example", "key": "tk", "graphql_key": ""},
    ]
    # Warm the cache.
    client.get("/api/resources/")
    import app.routes.resources as rr
    assert rr._resource_cache  # populated

    # Switch envs; cache should be wiped.
    client.post("/api/env/switch", json={"name": "Test"})
    assert rr._resource_cache == []
    assert rr._resource_source == ""


def test_graphql_schema_resource_synthesis_collapses_versions():
    """Same resource at multiple versions collapses to one entry with all
    versions listed under representations."""
    from app.routes.graphql_routes import _resources_from_graphql_schema
    schema = {
        "queryType": {"name": "Query"},
        "types": [{
            "name": "Query",
            "kind": "OBJECT",
            "fields": [
                {"name": "persons16", "type": {"name": "X", "kind": "OBJECT"}},
                {"name": "persons17", "type": {"name": "X", "kind": "OBJECT"}},
            ],
        }],
    }
    items = _resources_from_graphql_schema(schema)
    assert len(items) == 1
    assert items[0]["name"] == "persons"
    assert items[0]["versions"] == ["17", "16"]
    assert items[0]["latestVersion"] == "17"


def test_resources_cn_enabled(client, mock_ethos):
    r = client.get("/api/resources/cn-enabled")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data


def test_resources_annotations_returns_items_key(client):
    r = client.get("/api/resources/annotations")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_annotate_resource(client):
    payload = {
        "notes": "Test note",
        "trigger_conditions_gap": True,
        "updated_by": "pytest",
    }
    r = client.put("/api/resources/courses/annotate", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["resource_name"] == "courses"
    assert data["trigger_conditions_gap"] is True
    assert data["notes"] == "Test note"


def test_annotate_idempotent(client):
    payload = {"notes": "updated", "trigger_conditions_gap": False, "updated_by": "pytest"}
    client.put("/api/resources/sections/annotate", json=payload)
    r = client.put("/api/resources/sections/annotate", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["notes"] == "updated"
    assert data["trigger_conditions_gap"] is False


def test_annotations_list_after_upsert(client):
    client.put("/api/resources/persons/annotate",
               json={"notes": "n", "trigger_conditions_gap": False, "updated_by": "t"})
    r = client.get("/api/resources/annotations")
    data = r.get_json()
    names = [a["resource_name"] for a in data["items"]]
    assert "persons" in names
