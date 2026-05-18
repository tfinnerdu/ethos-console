"""Tests for /api/resources endpoints."""


def test_resources_list(client, mock_ethos):
    r = client.get("/api/resources/")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data


def test_resources_cn_enabled(client, mock_ethos):
    r = client.get("/api/resources/cn-enabled")
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data


def test_resources_annotations_empty(client):
    r = client.get("/api/resources/annotations")
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_annotate_resource(client):
    payload = {
        "notes": "Test note",
        "trigger_conditions_gap": True,
        "updated_by": "pytest",
    }
    r = client.put("/api/resources/persons/annotate", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["resource_name"] == "persons"
    assert data["trigger_conditions_gap"] is True
    assert data["notes"] == "Test note"


def test_annotate_idempotent(client):
    payload = {"notes": "updated", "trigger_conditions_gap": False, "updated_by": "pytest"}
    client.put("/api/resources/persons/annotate", json=payload)
    r = client.put("/api/resources/persons/annotate", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["notes"] == "updated"
    assert data["trigger_conditions_gap"] is False


def test_annotations_list_after_upsert(client):
    r = client.get("/api/resources/annotations")
    data = r.get_json()
    names = [a["resource_name"] for a in data]
    assert "persons" in names
