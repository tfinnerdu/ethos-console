"""Tests for the single-credential login gate — app/auth.py, app/routes/auth.py.

This is the one test file in the suite that builds its own app instance
without TESTING=True, so the before_request gate in app/auth.py actually
runs. Every other test file gets a free pass from the gate (it returns
immediately when `current_app.testing` is true) via the shared session `app`
fixture in conftest.py, which already sets TESTING=True — so none of the
other test files needed to change for this feature.

Credentials are set via app.config[...] (not monkeypatch.setenv) because
config.py's Config class reads os.environ once, at import time, into frozen
class attributes — the same reason the old CONSOLE_KEY-based tests mutated
app.config directly instead of the environment.
"""
from unittest.mock import patch

import pytest

from app import auth, create_app

REAL_SECRET_KEY = "a-real-random-test-signing-key-not-the-default"


def _make_app(secret_key):
    with patch("app.ethos_client.EthosClient.is_configured", return_value=False):
        test_app = create_app("development")
    test_app.config.update(
        TESTING=False,
        # Flask lazily sets the "app"-named logger to DEBUG the first time
        # app.logger is touched on a DEBUG=True app (e.g. while handling a
        # real client request below). "app.health_monitor" is a child logger
        # that would inherit that level — and uopy (imported by
        # unidata_client.py) globally reclasses every not-yet-created logger
        # as its own UOLogger the moment it's imported, whose debug()
        # override has a real arg-count bug once DEBUG-enabled. Keep this
        # False so this file (the one place real HTTP requests hit a
        # non-TESTING app) can't flip that on for the rest of the suite.
        DEBUG=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SECRET_KEY=secret_key,
    )
    with test_app.app_context():
        from app.database import db as _db
        _db.create_all()
    return test_app


@pytest.fixture()
def unconfigured_client(monkeypatch):
    monkeypatch.setattr(auth, "_FAILED_LOGIN_DELAY_SECONDS", 0)
    app = _make_app(REAL_SECRET_KEY)
    app.config["AUTH_USERNAME"] = ""
    app.config["AUTH_PASSWORD"] = ""
    return app.test_client()


@pytest.fixture()
def default_secret_key_client(monkeypatch):
    monkeypatch.setattr(auth, "_FAILED_LOGIN_DELAY_SECONDS", 0)
    app = _make_app(auth.DEFAULT_SECRET_KEY)
    app.config["AUTH_USERNAME"] = "admin"
    app.config["AUTH_PASSWORD"] = "correct-horse"
    return app.test_client()


@pytest.fixture()
def configured_client(monkeypatch):
    monkeypatch.setattr(auth, "_FAILED_LOGIN_DELAY_SECONDS", 0)
    app = _make_app(REAL_SECRET_KEY)
    app.config["AUTH_USERNAME"] = "admin"
    app.config["AUTH_PASSWORD"] = "correct-horse"
    return app.test_client()


def _login(client, username="admin", password="correct-horse", next_path=None):
    data = {"username": username, "password": password}
    if next_path is not None:
        data["next"] = next_path
    return client.post("/login", data=data)


class TestFailClosedWhenUnconfigured:
    def test_home_page_redirects_to_login(self, unconfigured_client):
        resp = unconfigured_client.get("/")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_login_page_shows_not_configured_notice(self, unconfigured_client):
        resp = unconfigured_client.get("/login")
        assert resp.status_code == 503
        assert b"not configured" in resp.data.lower()

    def test_login_post_also_blocked(self, unconfigured_client):
        resp = _login(unconfigured_client)
        assert resp.status_code == 503

    def test_api_route_returns_503_json(self, unconfigured_client):
        resp = unconfigured_client.get("/api/dob-repair/status")
        assert resp.status_code == 503
        assert "not configured" in resp.get_json()["error"].lower()

    def test_existing_page_also_gated(self, unconfigured_client):
        """Mnemonics used to be @login_required; confirm the global gate
        still protects it now that the decorator is gone."""
        resp = unconfigured_client.get("/mnemonics")
        assert resp.status_code == 302

    def test_health_live_still_exempt(self, unconfigured_client):
        resp = unconfigured_client.get("/api/health/live")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}


class TestFailClosedWhenSecretKeyIsDefault:
    """Credentials ARE set here, but SECRET_KEY is still the public default —
    the gate must treat this exactly like unconfigured, since a default
    SECRET_KEY makes the session cookie forgeable."""

    def test_home_page_still_blocked(self, default_secret_key_client):
        resp = default_secret_key_client.get("/")
        assert resp.status_code == 302

    def test_api_route_still_503(self, default_secret_key_client):
        resp = default_secret_key_client.get("/api/dob-repair/status")
        assert resp.status_code == 503

    def test_correct_credentials_do_not_help(self, default_secret_key_client):
        resp = _login(default_secret_key_client)
        assert resp.status_code == 503

    def test_health_live_still_exempt(self, default_secret_key_client):
        resp = default_secret_key_client.get("/api/health/live")
        assert resp.status_code == 200


class TestGateWhenConfiguredButNotLoggedIn:
    def test_home_page_redirects_with_next(self, configured_client):
        resp = configured_client.get("/")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_api_route_returns_401(self, configured_client):
        resp = configured_client.get("/api/dob-repair/status")
        assert resp.status_code == 401

    def test_bare_health_route_gated(self, configured_client):
        """/api/health/ (bare) was @api_auth_required before; stays gated."""
        resp = configured_client.get("/api/health/")
        assert resp.status_code == 401

    def test_health_token_now_gated(self, configured_client):
        """/api/health/token had NO decorator before (a real gap) — the
        global gate tightens this rather than exempting it."""
        resp = configured_client.get("/api/health/token")
        assert resp.status_code == 401

    def test_login_page_renders_form(self, configured_client):
        resp = configured_client.get("/login")
        assert resp.status_code == 200
        assert b"username" in resp.data.lower()
        assert b"password" in resp.data.lower()

    def test_login_page_preserves_next_param(self, configured_client):
        resp = configured_client.get("/login?next=/dob-repair")
        assert b"/dob-repair" in resp.data

    def test_health_live_still_exempt(self, configured_client):
        resp = configured_client.get("/api/health/live")
        assert resp.status_code == 200


class TestLoginFlow:
    def test_wrong_password_rejected(self, configured_client):
        resp = _login(configured_client, password="wrong")
        assert resp.status_code == 401
        assert b"Invalid username or password" in resp.data
        assert configured_client.get("/api/dob-repair/status").status_code == 401

    def test_wrong_username_rejected(self, configured_client):
        resp = _login(configured_client, username="not-admin")
        assert resp.status_code == 401

    def test_error_message_does_not_reveal_which_field_was_wrong(self, configured_client):
        wrong_user = _login(configured_client, username="nope").data
        wrong_pass = _login(configured_client, password="nope").data
        assert wrong_user == wrong_pass

    def test_correct_credentials_grant_access(self, configured_client):
        resp = _login(configured_client)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/")
        follow_up = configured_client.get("/api/dob-repair/status")
        assert follow_up.status_code == 200

    def test_correct_credentials_unlock_existing_page(self, configured_client):
        _login(configured_client)
        assert configured_client.get("/mnemonics").status_code == 200

    def test_next_param_relative_path_honored(self, configured_client):
        resp = _login(configured_client, next_path="/dob-repair")
        assert resp.headers["Location"].endswith("/dob-repair")

    def test_next_param_absolute_url_rejected(self, configured_client):
        resp = _login(configured_client, next_path="http://evil.example.com/steal")
        assert resp.headers["Location"].endswith("/")
        assert "evil.example.com" not in resp.headers["Location"]

    def test_next_param_protocol_relative_rejected(self, configured_client):
        resp = _login(configured_client, next_path="//evil.example.com/steal")
        assert resp.headers["Location"].endswith("/")
        assert "evil.example.com" not in resp.headers["Location"]

    def test_already_authenticated_login_page_redirects_away(self, configured_client):
        _login(configured_client)
        resp = configured_client.get("/login")
        assert resp.status_code == 302

    def test_logout_clears_session(self, configured_client):
        _login(configured_client)
        assert configured_client.get("/api/dob-repair/status").status_code == 200

        logout_resp = configured_client.get("/logout")
        assert logout_resp.status_code == 302
        assert logout_resp.headers["Location"].endswith("/login")

        assert configured_client.get("/api/dob-repair/status").status_code == 401
