"""Tests for the DEFAULT_ENV pre-select + active-env credential wiring."""
from app import create_app


_ENVS = [
    {"name": "Dev",  "url": "https://dev.example",  "key": "dev-key",  "graphql_key": ""},
    {"name": "Test", "url": "https://test.example", "key": "test-key", "graphql_key": "test-graphql-key"},
    {"name": "Prod", "url": "https://prod.example", "key": "prod-key", "graphql_key": ""},
]

_BASE_OVERRIDES = {
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "CONSOLE_KEY": "",
    "ETHOS_ENVIRONMENTS": _ENVS,
}


def _make_app(**extra):
    return create_app("development", overrides={**_BASE_OVERRIDES, **extra})


def test_default_env_matches_an_environment(monkeypatch):
    """DEFAULT_ENV=Test → current env is Test, client uses Test credentials."""
    app = _make_app(DEFAULT_ENV="Test")
    assert app.extensions["current_env_name"] == "Test"
    ethos = app.extensions["ethos_client"]
    assert ethos.api_key == "test-key"
    assert ethos.base_url == "https://test.example"


def test_default_env_is_case_insensitive():
    """DEFAULT_ENV=prod matches "Prod" without exact case."""
    app = _make_app(DEFAULT_ENV="prod")
    assert app.extensions["current_env_name"] == "Prod"
    assert app.extensions["ethos_client"].api_key == "prod-key"


def test_default_env_falls_back_to_first_when_unmatched(caplog):
    """An unrecognised DEFAULT_ENV logs a warning and falls back to envs[0]."""
    import logging
    with caplog.at_level(logging.WARNING):
        app = _make_app(DEFAULT_ENV="Staging")
    assert app.extensions["current_env_name"] == "Dev"
    assert app.extensions["ethos_client"].api_key == "dev-key"
    assert any("DEFAULT_ENV" in r.message and "Staging" in r.message for r in caplog.records)


def test_no_default_env_uses_first_configured_env():
    """No DEFAULT_ENV set → first ETHOS_ENV_n wins (existing behaviour)."""
    app = _make_app(DEFAULT_ENV="")
    assert app.extensions["current_env_name"] == "Dev"
    assert app.extensions["ethos_client"].api_key == "dev-key"


def test_no_environments_leaves_client_unconfigured(caplog):
    """Without any ETHOS_ENV_n, the EthosClient is unconfigured and Ethos-
    dependent tabs surface their 503 setup state. A startup warning fires."""
    import logging
    with caplog.at_level(logging.WARNING):
        app = _make_app(ETHOS_ENVIRONMENTS=[], DEFAULT_ENV="Whatever")
    assert app.extensions["current_env_name"] == ""
    ethos = app.extensions["ethos_client"]
    assert ethos.api_key == ""
    assert ethos.is_configured() is False
    assert any("No ETHOS_ENV_n configured" in r.message for r in caplog.records)


def test_graphql_helper_uses_env_specific_key_when_set(app):
    """If active env carries a graphql_key, _get_graphql_ethos returns a
    client built with that key instead of the bus key."""
    # Reuse the session-scoped app fixture but install our envs + switch to Test.
    app.config["ETHOS_ENVIRONMENTS"] = _ENVS
    app.extensions["current_env_name"] = "Test"
    from app.routes.graphql_routes import _get_graphql_ethos
    with app.test_request_context():
        client = _get_graphql_ethos()
    assert client.api_key == "test-graphql-key"
    assert client.base_url == "https://test.example"


def test_graphql_helper_falls_back_to_bus_client_when_no_graphql_key(app):
    """When the active env has no graphql_key, GraphQL uses the regular
    bus EthosClient (no extra construction)."""
    app.config["ETHOS_ENVIRONMENTS"] = _ENVS
    app.extensions["current_env_name"] = "Dev"
    from app.routes.graphql_routes import _get_graphql_ethos
    with app.test_request_context():
        client = _get_graphql_ethos()
    assert client is app.extensions["ethos_client"]


def test_default_env_does_not_break_mock_mode():
    """Mock mode ignores DEFAULT_ENV for credentials but honours it for the
    display name so the dropdown selection stays consistent."""
    app = _make_app(DEFAULT_ENV="Prod", CONSOLE_MOCK_MODE=True)
    assert app.extensions["mock_mode"] is True
    assert app.extensions["current_env_name"] == "Prod"
    # Mock client — credentials are MOCK fixtures, not the env's real key.
    assert app.extensions["ethos_client"].api_key != "prod-key"
