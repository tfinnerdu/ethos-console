"""Contract / characterization tests — hardcoded known-good values.

These tests do NOT check behavior.  They lock down specific invariants
that other code depends on implicitly.  If you change something and one
of these fails, that's the test doing its job: you need to consciously
update BOTH the implementation AND this expectation.

Philosophy: "If it's too awkward to test dynamically, freeze the known
answer and let the test shout when the answer changes."
"""
import pytest
from app.database import (
    ColleagueMnemonic,
    ReplayHistory,
    EthosErrorLog,
    ResourceAnnotation,
    SavedQuery,
    SEED_SAVED_QUERIES,
    db,
)
from app.routes import graphql_routes


# ── Model to_dict() key contracts ─────────────────────────────────────────────
# If a field is added to or removed from to_dict(), downstream consumers
# (JS, tests, exports) may silently break. These tests catch that.

MNEMONIC_DICT_KEYS = {
    "id", "mnemonic", "colleague_file", "eedm_resource", "eedm_version",
    "cn_supported", "cn_notes", "field_mappings", "gotchas",
    "related_mnemonics", "last_updated", "updated_by",
}

REPLAY_DICT_KEYS = {
    "id", "replayed_at", "source_message_id", "resource_name",
    "operation", "workflow_name", "conductor_url", "conductor_workflow_id",
    "outcome", "error_message",
}

ERROR_LOG_DICT_KEYS = {
    "id", "timestamp", "source", "endpoint",
    "http_status", "error_message", "resource_name",
}

ANNOTATION_DICT_KEYS = {
    "id", "resource_name", "trigger_conditions_gap",
    "notes", "updated_by", "last_updated",
}

SAVED_QUERY_DICT_KEYS = {
    "id", "name", "description", "query_text",
    "variables", "is_preloaded", "created_at", "updated_by",
}


def test_mnemonic_to_dict_keys(app):
    with app.app_context():
        obj = ColleagueMnemonic(mnemonic="TEST", colleague_file="TEST",
                                eedm_resource="test", eedm_version="1")
        db.session.add(obj)
        db.session.flush()
        assert set(obj.to_dict().keys()) == MNEMONIC_DICT_KEYS


def test_replay_history_to_dict_keys(app):
    with app.app_context():
        obj = ReplayHistory(source_message_id="x", resource_name="persons",
                            operation="updated", workflow_name="wf",
                            conductor_url="http://c/", outcome="success")
        db.session.add(obj)
        db.session.flush()
        assert set(obj.to_dict().keys()) == REPLAY_DICT_KEYS


def test_error_log_to_dict_keys(app):
    with app.app_context():
        obj = EthosErrorLog(source="test", endpoint="/api/x",
                            http_status=500, error_message="boom")
        db.session.add(obj)
        db.session.flush()
        assert set(obj.to_dict().keys()) == ERROR_LOG_DICT_KEYS


def test_annotation_to_dict_keys(app):
    with app.app_context():
        obj = ResourceAnnotation(resource_name="test-resource",
                                 trigger_conditions_gap=False)
        db.session.add(obj)
        db.session.flush()
        assert set(obj.to_dict().keys()) == ANNOTATION_DICT_KEYS


def test_saved_query_to_dict_keys(app):
    with app.app_context():
        obj = SavedQuery(name="Test", query_text="{ persons16 { edges { node { id } } } }")
        db.session.add(obj)
        db.session.flush()
        assert set(obj.to_dict().keys()) == SAVED_QUERY_DICT_KEYS


# ── Seeded saved query contract ───────────────────────────────────────────────
# Exactly these 5 names, all preloaded. Order is not mandated but the set is.

EXPECTED_PRELOADED_QUERY_NAMES = {
    "Person by ID — names + credentials",
    "Student academic programs",
    "Sections with meetings",
    "Person addresses",
    "Applications (admissions)",
}


def test_seed_saved_queries_count():
    """Exactly 5 preloaded queries are defined."""
    assert len(SEED_SAVED_QUERIES) == 5


def test_seed_saved_queries_names():
    """Every preloaded query has the expected name."""
    names = {q["name"] for q in SEED_SAVED_QUERIES}
    assert names == EXPECTED_PRELOADED_QUERY_NAMES


def test_seed_saved_queries_all_preloaded():
    """Every seed entry must be marked is_preloaded=True."""
    assert all(q["is_preloaded"] for q in SEED_SAVED_QUERIES)


def test_seed_saved_queries_have_variables():
    """Every seed entry must declare a variables dict (even if empty)."""
    for q in SEED_SAVED_QUERIES:
        assert "variables" in q, f"Query '{q['name']}' missing 'variables' key"
        assert isinstance(q["variables"], dict)


def test_seeded_queries_in_db(app):
    """After app startup the DB contains all 5 preloaded queries."""
    with app.app_context():
        preloaded = SavedQuery.query.filter_by(is_preloaded=True).all()
        names = {q.name for q in preloaded}
        assert names == EXPECTED_PRELOADED_QUERY_NAMES


# ── Blueprint URL prefix contract ─────────────────────────────────────────────
# If a prefix is changed, every JS fetch() call and every curl in docs breaks.

EXPECTED_PREFIXES = {
    "/api/bus",
    "/api/health",
    "/api/replay",
    "/api/mnemonics",
    "/api/resources",
    "/api/graphql-console",
    "/api/errors",
    "/api/schema-browser",
    "/api/phase3",
    "/api/cn",
}


def test_blueprint_url_prefixes_registered(app):
    """All expected API prefixes exist in the URL map."""
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    for prefix in EXPECTED_PREFIXES:
        matching = [r for r in rules if r.startswith(prefix)]
        assert matching, f"No routes found under prefix '{prefix}'"


def test_login_and_logout_routes_exist(app):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/login" in rules
    assert "/logout" in rules


# ── Schema cache TTL contract ─────────────────────────────────────────────────
# This drives the tooltip copy in graphql.html. Change TTL → update the UI copy too.

def test_schema_cache_ttl_is_4_hours():
    """Schema cache TTL is exactly 4 hours (14400 seconds)."""
    assert graphql_routes.SCHEMA_CACHE_TTL == 14_400


# ── Auth contract ─────────────────────────────────────────────────────────────

def test_auth_open_when_no_key(app):
    """With no CONSOLE_KEY set, every page is accessible without login."""
    assert not app.config.get("CONSOLE_KEY"), "This test requires CONSOLE_KEY to be empty"
    r = app.test_client().get("/")
    assert r.status_code == 200


def test_auth_redirects_when_key_set(app):
    """When CONSOLE_KEY is set and no session exists, HTML routes redirect to /login."""
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = "test-secret"
        r = app.test_client().get("/")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]
    finally:
        app.config["CONSOLE_KEY"] = original


def test_auth_wrong_key_returns_login_with_error(app):
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = "correct-secret"
        r = app.test_client().post("/login",
                                   data={"key": "wrong-secret", "next": "/"},
                                   follow_redirects=False)
        assert r.status_code == 200
        assert b"Invalid access key" in r.data
    finally:
        app.config["CONSOLE_KEY"] = original


def test_auth_correct_key_grants_access(app):
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = "correct-secret"
        client = app.test_client()
        r = client.post("/login",
                        data={"key": "correct-secret", "next": "/"},
                        follow_redirects=True)
        assert r.status_code == 200
    finally:
        app.config["CONSOLE_KEY"] = original


# ── Phase 3 "not configured" response contract ────────────────────────────────
# JS reads these exact keys to show the setup guide in the UI.

def test_phase3_field_diff_503_shape(client):
    r = client.get("/api/phase3/field-diff/persons")
    assert r.status_code == 503
    data = r.get_json()
    assert "error" in data
    assert "setup" in data
    assert "UNIDATA_HOST" in data["setup"]


def test_phase3_colleague_query_503_shape(client):
    r = client.post("/api/phase3/colleague-query",
                    json={"statement": "SELECT ID FROM PERSON"})
    assert r.status_code == 503
    data = r.get_json()
    assert "error" in data
    assert "setup" in data


def test_phase3_unidata_files_503(client):
    r = client.get("/api/phase3/unidata-files")
    assert r.status_code == 503


def test_phase3_colleague_files_503(client):
    r = client.get("/api/phase3/colleague-files")
    assert r.status_code == 503
    data = r.get_json()
    assert "error" in data
    assert "setup" in data


# ── Error CSV column order contract ───────────────────────────────────────────
# Any consumer parsing the CSV (downstream scripts, Excel macros) depends on
# column order being stable.

EXPECTED_CSV_COLUMNS = ["id", "timestamp", "source", "endpoint",
                        "http_status", "error_message", "resource_name"]


def test_error_csv_column_order(client):
    r = client.get("/api/errors/export")
    assert r.status_code == 200
    assert "text/csv" in r.content_type
    first_line = r.data.decode().split("\r\n")[0]
    assert first_line == ",".join(EXPECTED_CSV_COLUMNS)


# ── Health response key contract ──────────────────────────────────────────────

EXPECTED_HEALTH_KEYS = {
    "token", "queue_depth", "queue_status", "queue_error",
    "latency", "recent_errors", "error_count_1h",
    "error_status", "resource_health", "ethos_configured",
    "mock",
}

EXPECTED_LATENCY_KEYS = {"p50", "p95", "p99", "max", "sample_count"}


def test_health_response_keys(client):
    data = client.get("/api/health/").get_json()
    assert set(data.keys()) == EXPECTED_HEALTH_KEYS


def test_health_latency_keys(client):
    data = client.get("/api/health/").get_json()
    assert set(data["latency"].keys()) == EXPECTED_LATENCY_KEYS


def test_health_live_always_200(client):
    """Liveness probe must always return exactly {status: ok}."""
    r = client.get("/api/health/live")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


# ── Seeded mnemonic count ─────────────────────────────────────────────────────
# SEED_MNEMONICS is the source of truth for the initial knowledge base.
# Adding entries is fine; accidental deletion of existing ones is not.

def test_seed_mnemonic_count(app):
    from app.database import SEED_MNEMONICS
    assert len(SEED_MNEMONICS) >= 8, (
        f"Expected at least 8 seed mnemonics, found {len(SEED_MNEMONICS)}. "
        "If you removed one intentionally, update this lower bound."
    )
