"""Tests for /api/env endpoints — environment listing and switching.

Not previously covered: no test_env.py existed (flagged by the standards
audit — env.py wasn't in docs/test-coverage-classification.md and its own
route contract was never asserted, only exercised incidentally as a
cache-invalidation side effect from tests/test_resources_api.py).
"""
import pytest
from app.database import AuditEntry


@pytest.fixture(autouse=True)
def _restore_env_config(app):
    """The `app` fixture is session-scoped (tests/conftest.py) -- restore
    ETHOS_ENVIRONMENTS and the ethos_client's credentials after each test so
    a switch performed here doesn't leak into later test files."""
    orig_envs = app.config.get("ETHOS_ENVIRONMENTS", [])
    ethos = app.extensions["ethos_client"]
    orig_key, orig_url = ethos.api_key, ethos.base_url
    orig_current = app.extensions.get("current_env_name", "")
    yield
    app.config["ETHOS_ENVIRONMENTS"] = orig_envs
    ethos.api_key, ethos.base_url = orig_key, orig_url
    app.extensions["current_env_name"] = orig_current


def test_list_environments_shape(client):
    r = client.get("/api/env/")
    assert r.status_code == 200
    data = r.get_json()
    assert "environments" in data
    assert "current" in data


def test_list_environments_empty_by_default(client, app):
    # Other test files (test_default_env.py) mutate this same session-scoped
    # app's ETHOS_ENVIRONMENTS without reverting it -- set it explicitly here
    # rather than assume a pristine baseline across the whole test session.
    app.config["ETHOS_ENVIRONMENTS"] = []
    data = client.get("/api/env/").get_json()
    assert data["environments"] == []


def test_switch_unknown_environment_returns_404(client):
    r = client.post("/api/env/switch", json={"name": "DoesNotExist"})
    assert r.status_code == 404
    assert "error" in r.get_json()


def test_switch_missing_name_returns_404(client):
    r = client.post("/api/env/switch", json={})
    assert r.status_code == 404


def test_switch_non_object_json_body_does_not_500(client):
    r = client.post("/api/env/switch", data="null", content_type="application/json")
    assert r.status_code == 404  # coerces to {}, then "name '' not found"


def test_switch_success_updates_current_and_credentials(client, app):
    app.config["ETHOS_ENVIRONMENTS"] = [
        {"name": "Dev", "url": "https://dev.example", "key": "dev-key", "graphql_key": ""},
        {"name": "Test", "url": "https://test.example", "key": "test-key", "graphql_key": ""},
    ]
    r = client.post("/api/env/switch", json={"name": "Test"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["switched_to"] == "Test"
    assert data["url"] == "https://test.example"

    ethos = app.extensions["ethos_client"]
    assert ethos.api_key == "test-key"
    assert ethos.base_url == "https://test.example"

    listed = client.get("/api/env/").get_json()
    assert listed["current"] == "Test"


def test_switch_emits_audit_event(client, app):
    app.config["ETHOS_ENVIRONMENTS"] = [
        {"name": "Dev", "url": "https://dev.example", "key": "dev-key", "graphql_key": ""},
    ]
    client.post("/api/env/switch", json={"name": "Dev"})
    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="switch", resource_type="ethos_environment", resource_id="Dev",
        ).first()
    assert entry is not None
    assert entry.detail["url"] == "https://dev.example"
