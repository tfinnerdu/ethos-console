"""Tests for /api/mnemonics endpoints — full CRUD coverage."""
import itertools
from app.database import db, ColleagueMnemonic

_counter = itertools.count(1)

_BASE = {"colleague_file": "TEST.FILE", "eedm_resource": "test-resource", "eedm_version": "1"}


def _create(client, overrides=None):
    """Create a mnemonic with a unique auto-generated name unless overridden."""
    payload = {**_BASE, "mnemonic": f"TST{next(_counter):04d}", **(overrides or {})}
    return client.post("/api/mnemonics/", json=payload)


# ── List ──────────────────────────────────────────────────────────────────────

def test_list_returns_array(client):
    r = client.get("/api/mnemonics/")
    assert r.status_code == 200
    assert isinstance(r.get_json(), list)


def test_list_includes_seeded_mnemonics(client):
    items = client.get("/api/mnemonics/").get_json()
    mnemonics = [m["mnemonic"] for m in items]
    assert "PERSON" in mnemonics


def test_list_filter_by_mnemonic_name(client):
    items = client.get("/api/mnemonics/?q=PERSON").get_json()
    assert len(items) > 0
    # PERSON mnemonic is a known seed entry — must appear in filtered results
    assert any(m["mnemonic"] == "PERSON" for m in items)
    # Every result must have "person" in at least one searched field
    searchable_fields = ("mnemonic", "colleague_file", "eedm_resource", "gotchas", "cn_notes")
    assert all(
        any("person" in (m.get(f) or "").lower() for f in searchable_fields)
        for m in items
    )


def test_list_filter_no_match_returns_empty(client):
    items = client.get("/api/mnemonics/?q=ZZZNOMATCH999").get_json()
    assert items == []


def test_list_ordered_alphabetically(client):
    items = client.get("/api/mnemonics/").get_json()
    names = [m["mnemonic"] for m in items]
    assert names == sorted(names)


# ── Get by ID ─────────────────────────────────────────────────────────────────

def test_get_existing_mnemonic(client):
    created = _create(client).get_json()
    r = client.get(f"/api/mnemonics/{created['id']}")
    assert r.status_code == 200
    assert r.get_json()["id"] == created["id"]


def test_get_unknown_id_returns_404(client):
    r = client.get("/api/mnemonics/999999")
    assert r.status_code == 404


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_returns_201(client):
    r = _create(client)
    assert r.status_code == 201


def test_create_stores_mnemonic_uppercased(client):
    r = _create(client, {"mnemonic": "lowercase"})
    assert r.status_code == 201
    assert r.get_json()["mnemonic"] == "LOWERCASE"


def test_create_missing_mnemonic_returns_400(client):
    r = client.post("/api/mnemonics/", json={"colleague_file": "X"})
    assert r.status_code == 400
    assert "mnemonic" in r.get_json()["error"].lower()


def test_create_duplicate_returns_409(client):
    _create(client, {"mnemonic": "DUPMNEM"})
    r = _create(client, {"mnemonic": "DUPMNEM"})
    assert r.status_code == 409
    assert "already exists" in r.get_json()["error"].lower()


def test_create_cn_supported_defaults_false(client):
    r = _create(client)
    assert r.get_json()["cn_supported"] is False


def test_create_with_all_optional_fields(client):
    payload = {
        **_BASE,
        "mnemonic": "FULLTEST",
        "cn_supported": True,
        "cn_notes": "Some notes",
        "gotchas": "Watch out",
        "field_mappings": [{"eedm": "firstName", "colleague": "FIRST.NAME"}],
        "related_mnemonics": ["PERSON"],
        "updated_by": "pytest",
    }
    r = client.post("/api/mnemonics/", json=payload)
    assert r.status_code == 201
    data = r.get_json()
    assert data["cn_supported"] is True
    assert data["cn_notes"] == "Some notes"
    assert data["gotchas"] == "Watch out"
    assert data["field_mappings"] == [{"eedm": "firstName", "colleague": "FIRST.NAME"}]
    assert data["related_mnemonics"] == ["PERSON"]
    assert data["updated_by"] == "pytest"


# ── Update ────────────────────────────────────────────────────────────────────

def test_update_returns_200(client):
    item_id = _create(client).get_json()["id"]
    r = client.put(f"/api/mnemonics/{item_id}", json={"cn_notes": "updated notes"})
    assert r.status_code == 200


def test_update_modifies_field(client):
    item_id = _create(client).get_json()["id"]
    client.put(f"/api/mnemonics/{item_id}", json={"cn_supported": True, "eedm_version": "2"})
    data = client.get(f"/api/mnemonics/{item_id}").get_json()
    assert data["cn_supported"] is True
    assert data["eedm_version"] == "2"


def test_update_sets_last_updated(client):
    item_id = _create(client).get_json()["id"]
    client.put(f"/api/mnemonics/{item_id}", json={"cn_notes": "changed"})
    after = client.get(f"/api/mnemonics/{item_id}").get_json()["last_updated"]
    assert after is not None


def test_update_unknown_id_returns_404(client):
    r = client.put("/api/mnemonics/999999", json={"cn_notes": "x"})
    assert r.status_code == 404


def test_update_partial_leaves_other_fields(client):
    item_id = _create(client, {"cn_notes": "orig"}).get_json()["id"]
    client.put(f"/api/mnemonics/{item_id}", json={"eedm_version": "9"})
    data = client.get(f"/api/mnemonics/{item_id}").get_json()
    assert data["cn_notes"] == "orig"
    assert data["eedm_version"] == "9"


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_returns_204(client):
    item_id = _create(client).get_json()["id"]
    r = client.delete(f"/api/mnemonics/{item_id}")
    assert r.status_code == 204


def test_delete_removes_from_db(client):
    item_id = _create(client).get_json()["id"]
    client.delete(f"/api/mnemonics/{item_id}")
    r = client.get(f"/api/mnemonics/{item_id}")
    assert r.status_code == 404


def test_delete_unknown_id_returns_404(client):
    r = client.delete("/api/mnemonics/999999")
    assert r.status_code == 404


def test_create_non_object_json_body_returns_400_not_500(client):
    r = client.post("/api/mnemonics/", data="null", content_type="application/json")
    assert r.status_code == 400


def test_update_non_object_json_body_is_a_no_op_not_a_500(client):
    # update_mnemonic has no required-field check (unlike create) -- a
    # non-dict body coerces to {}, which is a valid no-op update, not a
    # validation error. The regression this guards is the unhandled 500 a
    # bare scalar body used to cause, not a specific status code.
    item_id = _create(client).get_json()["id"]
    before = client.get(f"/api/mnemonics/{item_id}").get_json()
    r = client.put(f"/api/mnemonics/{item_id}", data="42", content_type="application/json")
    assert r.status_code == 200
    after = client.get(f"/api/mnemonics/{item_id}").get_json()
    assert after["colleague_file"] == before["colleague_file"]


def test_create_update_delete_emit_audit_events(client, app):
    from app.database import AuditEntry
    r = _create(client)
    mnemonic = r.get_json()["mnemonic"]
    item_id = r.get_json()["id"]

    client.put(f"/api/mnemonics/{item_id}", json={"gotchas": "updated"})
    client.delete(f"/api/mnemonics/{item_id}")

    with app.app_context():
        actions = {
            e.action for e in AuditEntry.query.filter_by(resource_id=mnemonic).all()
        }
    assert {"create", "update", "delete"} <= actions
