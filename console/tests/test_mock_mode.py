"""Tests for CONSOLE_MOCK_MODE.

Two roles:
1. Pin the three required mock-mode signals (header, badge, health key).
2. Characterization tests for each provider's fixture shape — when the
   fixture shape moves, the test fails and forces a conscious update.
"""
import pytest

from app import create_app
from app.database import db as _db


@pytest.fixture()
def mock_app():
    """An app created with CONSOLE_MOCK_MODE=True."""
    flask_app = create_app("development", overrides={
        "CONSOLE_MOCK_MODE": True,
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "CONSOLE_KEY": "",
    })
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture()
def mc(mock_app):
    return mock_app.test_client()


# ── Mock-mode signals ────────────────────────────────────────────────────────

def test_mock_mode_extension_flag_is_true(mock_app):
    assert mock_app.extensions["mock_mode"] is True


def test_x_mock_mode_header_set_on_api_responses(mc):
    r = mc.get("/api/resources/")
    assert r.headers.get("X-Mock-Mode") == "true"


def test_x_mock_mode_header_set_on_html_pages(mc):
    r = mc.get("/")
    assert r.headers.get("X-Mock-Mode") == "true"


def test_mock_badge_present_in_nav(mc):
    html = mc.get("/").get_data(as_text=True)
    assert "mock-badge" in html
    assert "MOCK" in html
    assert "CONSOLE_MOCK_MODE" in html  # tooltip text identifies the source


def test_no_live_badge_in_mock_mode(mc):
    # Live/mock must never both be shown — the badge should be one or the
    # other, never ambiguous or absent-by-omission in either state.
    html = mc.get("/").get_data(as_text=True)
    assert "live-badge" not in html


def test_health_endpoint_reports_mock_true(mc):
    data = mc.get("/api/health/").get_json()
    assert data["mock"] is True


def test_configured_features_all_true_in_mock(mc):
    # Every tab's "off" badge should be cleared when mock is on.
    html = mc.get("/").get_data(as_text=True)
    assert 'class="tab-off-badge"' not in html


# ── Real mode does NOT carry mock signals ────────────────────────────────────

@pytest.fixture()
def live_app():
    flask_app = create_app("development", overrides={
        "CONSOLE_MOCK_MODE": False,
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "CONSOLE_KEY": "",
    })
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


def test_live_mode_no_x_mock_header(live_app):
    r = live_app.test_client().get("/api/resources/")
    assert "X-Mock-Mode" not in r.headers


def test_live_mode_no_mock_badge(live_app):
    html = live_app.test_client().get("/").get_data(as_text=True)
    assert "mock-badge" not in html


def test_live_mode_shows_live_badge(live_app):
    # Live state must be an explicit positive signal, not just "MOCK is
    # absent" — an operator glancing at the nav should never have to infer
    # live-ness from the absence of something else.
    html = live_app.test_client().get("/").get_data(as_text=True)
    assert "live-badge" in html
    assert "LIVE" in html


def test_live_mode_health_reports_mock_false(live_app):
    data = live_app.test_client().get("/api/health/").get_json()
    assert data["mock"] is False


# ── Provider characterization: Ethos ─────────────────────────────────────────

def test_ethos_available_resources_shape(mock_app):
    ethos = mock_app.extensions["ethos_client"]
    items = ethos.get_available_resources()
    assert isinstance(items, list) and len(items) >= 10
    sample = next(r for r in items if r["name"] == "persons")
    assert sample["representations"][0]["X-Media-Type"].startswith(
        "application/vnd.hedtech.integration.v"
    )


def test_ethos_cn_resources_shape(mock_app):
    ethos = mock_app.extensions["ethos_client"]
    items = ethos.get_cn_available_resources()
    assert {"resourceName": "persons"} in items


def test_ethos_consume_messages_returns_shape_and_increments_id(mock_app):
    ethos = mock_app.extensions["ethos_client"]
    a = ethos.consume_messages()
    b = ethos.consume_messages()
    assert len(a) == 1 and len(b) == 1
    assert a[0]["id"] != b[0]["id"]
    assert "resource" in a[0] and "name" in a[0]["resource"]


def test_ethos_graphql_introspection_returns_schema(mock_app):
    ethos = mock_app.extensions["ethos_client"]
    result = ethos.graphql(
        "query IntrospectionQuery { __schema { queryType { name } types { name kind } } }"
    )
    schema = result["data"]["__schema"]
    assert schema["queryType"] == {"name": "Query"}
    type_names = {t["name"] for t in schema["types"]}
    assert "persons16" in type_names


def test_ethos_graphql_non_introspection_returns_mock_marker(mock_app):
    ethos = mock_app.extensions["ethos_client"]
    result = ethos.graphql("query { persons16 { id } }")
    assert result["data"]["_mock"] is True


def test_ethos_publish_notification_does_not_call_network(mock_app):
    ethos = mock_app.extensions["ethos_client"]
    r = ethos.publish_notification({"resource": {"name": "persons"}})
    assert r["status"] == "accepted"
    assert r["mock"] is True


# ── Provider characterization: CNM ───────────────────────────────────────────

def test_cn_repository_health_characterization(mock_app):
    repo = mock_app.extensions["cn_repository"]
    h = repo.get_health()
    assert h["status"] == "ok"
    assert h["mock"] is True


def test_cn_repository_notifications_filterable(mock_app):
    repo = mock_app.extensions["cn_repository"]
    items = repo.get_notifications(resource="persons")
    assert items and all("persons" in n["resourceName"] for n in items)


# ── Provider characterization: Colleague Web API ─────────────────────────────

def test_colleague_about_characterization(mock_app):
    cli = mock_app.extensions["colleague_api_client"]
    assert "Colleague" in cli.get_about()["productName"]


def test_colleague_transaction_echoes_input(mock_app):
    cli = mock_app.extensions["colleague_api_client"]
    out = cli.call_transaction("GET.PERSON.INFO", {"KEY.PERSON": ["B00001"]})
    assert out["_mock"] is True
    assert out["EchoInput"] == {"KEY.PERSON": ["B00001"]}


# ── Provider characterization: Conductor ─────────────────────────────────────

def test_conductor_trigger_returns_mock_id(mock_app):
    c = mock_app.extensions["conductor_client"]
    wid = c.trigger_workflow("EDA_Person_Sync", {"resource": {}, "content": {}})
    assert wid.startswith("mock-EDA_Person_Sync-")


# ── Provider characterization: UniData ───────────────────────────────────────

def test_unidata_list_files_returns_list(mock_app):
    u = mock_app.extensions["unidata_client"]
    files = u.list_files()
    assert "PERSON" in files


def test_unidata_command_for_read_verb(mock_app):
    u = mock_app.extensions["unidata_client"]
    out = u.run_command("LIST PERSON SAMPLE 3")
    assert "CONSOLE_MOCK_MODE" in out
    assert "records listed" in out


def test_unidata_command_for_write_verb_does_nothing(mock_app):
    u = mock_app.extensions["unidata_client"]
    out = u.run_command("DELETE PERSON 12345")
    assert "nothing happened" in out


def test_unidata_subroutine_returns_args(mock_app):
    u = mock_app.extensions["unidata_client"]
    r = u.call_subroutine("CALC.PERSON", [
        {"label": "INPUT", "direction": "in", "value": "B00001"},
        {"label": "OUT", "direction": "out", "value": ""},
    ])
    assert r["_mock"] is True
    assert r["args"][1]["value"].startswith("MOCK_OUT_")


# ── Provider characterization: DoaneEdgeGate ─────────────────────────────────

def test_edge_gate_health_characterization(mock_app):
    gate = mock_app.extensions["edge_gate_client"]
    h = gate.check_health()
    assert h["configured"] is True
    assert h["reachable"] is True
    assert h["status"] == "ok"


def test_edge_gate_health_endpoint_in_mock_mode_never_calls_out(mc):
    # A real requests.get would fail (no network) if the mock client didn't
    # override check_health() — the 200 here is the assertion.
    r = mc.get("/api/health/edge-gate")
    assert r.status_code == 200
    assert r.get_json()["configured"] is True


# ── End-to-end smoke: every tab renders in mock mode ─────────────────────────

@pytest.mark.parametrize("path", [
    "/", "/replay", "/graphql", "/schema-browser", "/resources", "/mnemonics",
    "/field-diff", "/colleague-query", "/colleague-api", "/cn-monitor", "/health", "/errors",
])
def test_every_tab_renders_in_mock_mode(mc, path):
    r = mc.get(path)
    assert r.status_code == 200, f"{path} returned {r.status_code}"
