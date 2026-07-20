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
    monkeypatch.setattr(auth, "_FAILED_LOGIN_BASE_DELAY_SECONDS", 0)
    app = _make_app(REAL_SECRET_KEY)
    app.config["AUTH_USERNAME"] = ""
    app.config["AUTH_PASSWORD"] = ""
    return app.test_client()


@pytest.fixture()
def default_secret_key_client(monkeypatch):
    monkeypatch.setattr(auth, "_FAILED_LOGIN_BASE_DELAY_SECONDS", 0)
    app = _make_app(auth.DEFAULT_SECRET_KEY)
    app.config["AUTH_USERNAME"] = "admin"
    app.config["AUTH_PASSWORD"] = "correct-horse"
    return app.test_client()


@pytest.fixture()
def configured_client(monkeypatch):
    monkeypatch.setattr(auth, "_FAILED_LOGIN_BASE_DELAY_SECONDS", 0)
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

    @pytest.mark.parametrize("payload", [
        "/\\evil.example.com/steal",
        "\\/evil.example.com/steal",
        "\\\\evil.example.com/steal",
    ])
    def test_next_param_backslash_protocol_relative_rejected(self, configured_client, payload):
        # Browsers normalize '\' to '/' when resolving http(s) URLs, so each
        # of these is equivalent to '//evil.example.com/steal' even though
        # none literally starts with "//" — a naive .startswith("//") check
        # would let them through.
        resp = _login(configured_client, next_path=payload)
        assert resp.headers["Location"].endswith("/")
        assert "evil.example.com" not in resp.headers["Location"]

    def test_next_param_single_backslash_same_origin_path_allowed(self, configured_client):
        # A single leading backslash normalizes to a single leading slash —
        # a same-origin absolute path, not a protocol-relative redirect —
        # so this one should be preserved rather than rejected.
        resp = _login(configured_client, next_path="\\dob-repair")
        assert resp.headers["Location"].endswith("/dob-repair")

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


@pytest.fixture()
def path_scoped_client(monkeypatch):
    """Same as configured_client, but with SESSION_COOKIE_PATH set — as a
    real deployment behind k8s/ethos-console.yaml's stripPrefix would have it."""
    monkeypatch.setattr(auth, "_FAILED_LOGIN_BASE_DELAY_SECONDS", 0)
    app = _make_app(REAL_SECRET_KEY)
    app.config["AUTH_USERNAME"] = "admin"
    app.config["AUTH_PASSWORD"] = "correct-horse"
    app.config["SESSION_COOKIE_PATH"] = "/prod/ethos-console"
    return app.test_client()


class TestSessionCookiePath:
    """Regression coverage: other apps live at their own prod/{appname} on
    the same origin as this one (behind du-int.doane.edu) — the session
    cookie must not default to Path=/, which would send it to all of them."""

    def test_default_path_is_root(self, configured_client):
        resp = _login(configured_client)
        cookies = resp.headers.get_all("Set-Cookie")
        assert any("session=" in c for c in cookies)
        assert not any("Path=/prod" in c for c in cookies)

    def test_configured_path_is_honored(self, path_scoped_client):
        resp = _login(path_scoped_client)
        cookies = resp.headers.get_all("Set-Cookie")
        assert any("Path=/prod/ethos-console" in c for c in cookies)


@pytest.fixture()
def throttled_client(monkeypatch):
    """Like configured_client, but keeps the real progressive failed-login
    backoff (record_failed_login) instead of zeroing it out — needed to
    actually exercise it. time.sleep is captured rather than invoked, so
    these tests don't spend real wall-clock time waiting."""
    app = _make_app(REAL_SECRET_KEY)
    app.config["AUTH_USERNAME"] = "admin"
    app.config["AUTH_PASSWORD"] = "correct-horse"
    sleeps = []
    monkeypatch.setattr(auth.time, "sleep", lambda seconds: sleeps.append(seconds))
    client = app.test_client()
    client.sleeps = sleeps
    return client


class TestFailedLoginProgressiveThrottle:
    """Regression coverage for the DoS risk in the old flat time.sleep(1.0):
    this app runs a single gunicorn worker with --threads 4 (Dockerfile), so
    4 concurrent bad logins used to freeze the entire console for a full
    second, repeatably, with no botnet required. The throttle now scales
    with recent-failure count per source IP instead of firing at full
    strength on every single attempt."""

    @pytest.fixture(autouse=True)
    def _clean_attempt_tracker(self):
        auth._failed_login_attempts.clear()
        yield
        auth._failed_login_attempts.clear()

    def test_first_failure_uses_base_delay(self, throttled_client):
        _login(throttled_client, password="wrong")
        assert throttled_client.sleeps == [auth._FAILED_LOGIN_BASE_DELAY_SECONDS]

    def test_delay_scales_with_recent_failure_count(self, throttled_client):
        for _ in range(3):
            _login(throttled_client, password="wrong")
        assert throttled_client.sleeps == [
            auth._FAILED_LOGIN_BASE_DELAY_SECONDS * 1,
            auth._FAILED_LOGIN_BASE_DELAY_SECONDS * 2,
            auth._FAILED_LOGIN_BASE_DELAY_SECONDS * 3,
        ]

    def test_delay_capped_at_max(self, throttled_client):
        attempts = int(auth._FAILED_LOGIN_MAX_DELAY_SECONDS / auth._FAILED_LOGIN_BASE_DELAY_SECONDS) + 5
        for _ in range(attempts):
            _login(throttled_client, password="wrong")
        assert throttled_client.sleeps[-1] == auth._FAILED_LOGIN_MAX_DELAY_SECONDS

    def test_successful_login_does_not_add_to_the_counter(self, throttled_client):
        _login(throttled_client, password="wrong")
        _login(throttled_client, password="wrong")
        _login(throttled_client)  # correct credentials this time — not yet authenticated, so this proceeds
        assert throttled_client.sleeps == [
            auth._FAILED_LOGIN_BASE_DELAY_SECONDS * 1,
            auth._FAILED_LOGIN_BASE_DELAY_SECONDS * 2,
        ]

    def test_different_source_ips_tracked_independently(self):
        now = 1_000_000.0
        assert auth._recent_failure_count("1.2.3.4", now) == 1
        assert auth._recent_failure_count("1.2.3.4", now) == 2
        assert auth._recent_failure_count("5.6.7.8", now) == 1

    def test_old_failures_outside_window_do_not_count(self):
        now = 1_000_000.0
        assert auth._recent_failure_count("9.9.9.9", now) == 1
        later = now + auth._FAILED_LOGIN_WINDOW_SECONDS + 1
        assert auth._recent_failure_count("9.9.9.9", later) == 1

    def test_tracked_ip_dict_is_swept_once_past_threshold(self):
        now = 1_000_000.0
        for i in range(auth._FAILED_LOGIN_TRACKED_IPS_SWEEP_THRESHOLD + 1):
            auth._recent_failure_count(f"10.0.{i // 256}.{i % 256}", now)
        stale_check_time = now + auth._FAILED_LOGIN_WINDOW_SECONDS + 1
        auth._recent_failure_count("fresh-ip", stale_check_time)
        assert len(auth._failed_login_attempts) < auth._FAILED_LOGIN_TRACKED_IPS_SWEEP_THRESHOLD + 2


# ── Entra ID (Azure AD) SSO ───────────────────────────────────────────────────
# See docs/auth-gate-guide.md's "Migrating to SSO" section. Per the
# reference pattern's own testing guidance: patch build_msal_app to return a
# fake client — the two routes never talk to msal directly, so nothing else
# needs mocking, and none of this touches the network or a real tenant.

class FakeMsalApp:
    def __init__(self, auth_url="https://login.microsoftonline.com/fake?mock=1", token_result=None):
        self.auth_url = auth_url
        self.token_result = token_result if token_result is not None else {}

    def get_authorization_request_url(self, scopes, **kwargs):
        return self.auth_url

    def acquire_token_by_authorization_code(self, code, **kwargs):
        return self.token_result


def _entra_env(app):
    app.config["ENTRA_TENANT_ID"] = "tenant-123"
    app.config["ENTRA_CLIENT_ID"] = "client-123"
    app.config["ENTRA_CLIENT_SECRET"] = "secret-123"
    app.config["ENTRA_REDIRECT_URI"] = "http://localhost/api/v1/auth/callback"


@pytest.fixture()
def entra_only_client(monkeypatch):
    """Entra configured; local username/password deliberately left unset —
    exercises the "SSO only, no fallback credential" deployment shape."""
    monkeypatch.setattr(auth, "_FAILED_LOGIN_BASE_DELAY_SECONDS", 0)
    app = _make_app(REAL_SECRET_KEY)
    app.config["AUTH_USERNAME"] = ""
    app.config["AUTH_PASSWORD"] = ""
    _entra_env(app)
    return app.test_client()


@pytest.fixture()
def entra_and_local_client(monkeypatch):
    """Both Entra and local credentials configured — the "fallback available"
    deployment shape this was actually built for."""
    monkeypatch.setattr(auth, "_FAILED_LOGIN_BASE_DELAY_SECONDS", 0)
    app = _make_app(REAL_SECRET_KEY)
    app.config["AUTH_USERNAME"] = "admin"
    app.config["AUTH_PASSWORD"] = "correct-horse"
    _entra_env(app)
    return app.test_client()


@pytest.fixture()
def entra_configured_default_secret_key_client(monkeypatch):
    """Entra IS configured, but SECRET_KEY is still the public default.

    Regression fixture for the auth-bypass-via-forged-session bug: previously
    the gate's fail-closed check only looked at SECRET_KEY via
    is_safely_configured(), which only gates the *local credentials* path —
    so this exact combination sailed straight past the gate with Entra never
    contacted, and a session cookie forged with the well-known default key
    was accepted as authenticated.
    """
    monkeypatch.setattr(auth, "_FAILED_LOGIN_BASE_DELAY_SECONDS", 0)
    app = _make_app(auth.DEFAULT_SECRET_KEY)
    app.config["AUTH_USERNAME"] = "admin"
    app.config["AUTH_PASSWORD"] = "correct-horse"
    _entra_env(app)
    return app.test_client()


def _stash_entra_session(client, state="expected-state", nonce="expected-nonce", next_path="/"):
    with client.session_transaction() as sess:
        sess["entra_state"] = state
        sess["entra_nonce"] = nonce
        sess["entra_next"] = next_path


class TestGateAutoRedirectsToEntra:
    def test_home_page_redirects_to_entra_not_local_login(self, entra_and_local_client):
        resp = entra_and_local_client.get("/")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login/entra?next=/")

    def test_api_route_still_returns_401_json_not_a_redirect(self, entra_and_local_client):
        resp = entra_and_local_client.get("/api/dob-repair/status")
        assert resp.status_code == 401

    def test_gate_does_not_fail_closed_when_only_entra_is_configured(self, entra_only_client):
        # Local credentials are unset here — without Entra this fixture
        # would 503 (see TestFailClosedWhenUnconfigured). Confirms Entra
        # alone is enough to satisfy the gate's "is auth configured" check.
        resp = entra_only_client.get("/")
        assert resp.status_code == 302
        assert "/login/entra" in resp.headers["Location"]

    def test_local_login_page_redirects_to_entra_when_local_creds_unset(self, entra_only_client):
        # Visiting /login directly with no local credentials configured
        # shouldn't show a form guaranteed to fail — go straight to Entra.
        resp = entra_only_client.get("/login")
        assert resp.status_code == 302
        assert "/login/entra" in resp.headers["Location"]

    def test_local_login_page_still_works_when_both_configured(self, entra_and_local_client):
        # /login stays a reachable manual fallback when local creds ARE set,
        # even though the gate itself prefers Entra.
        resp = entra_and_local_client.get("/login")
        assert resp.status_code == 200
        assert b"Sign in with Microsoft" in resp.data
        assert b"username" in resp.data.lower()

    def test_gate_falls_back_to_local_login_when_entra_not_configured(self, configured_client):
        # Regression guard: existing (no-Entra) fixture must redirect to the
        # LOCAL page specifically, not just "somewhere containing /login".
        resp = configured_client.get("/")
        assert resp.headers["Location"].endswith("/login?next=/")
        assert "/login/entra" not in resp.headers["Location"]


class TestFailClosedWhenEntraConfiguredButSecretKeyIsDefault:
    """Regression coverage: Entra configured + default SECRET_KEY must still
    fail closed, and /login must not loop by redirecting to Entra (which
    would just hit this same gate again after a successful Entra login)."""

    def test_home_page_blocked_not_redirected_to_entra(self, entra_configured_default_secret_key_client):
        resp = entra_configured_default_secret_key_client.get("/")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        assert "/login/entra" not in resp.headers["Location"]

    def test_api_route_returns_503(self, entra_configured_default_secret_key_client):
        resp = entra_configured_default_secret_key_client.get("/api/dob-repair/status")
        assert resp.status_code == 503
        assert "not configured" in resp.get_json()["error"].lower()

    def test_login_page_shows_not_configured_notice_without_redirecting_to_entra(
        self, entra_configured_default_secret_key_client,
    ):
        # This is the crux of the loop-avoidance fix: with local creds AND
        # Entra both configured, login_page() would normally prefer Entra
        # once is_safely_configured() fails — but is_safely_configured()
        # doesn't fail here (local creds are set), so the *unconditional*
        # secret_key_is_default() check has to be the thing that catches it,
        # ahead of any Entra redirect.
        resp = entra_configured_default_secret_key_client.get("/login")
        assert resp.status_code == 503
        assert b"not configured" in resp.data.lower()

    def test_health_live_still_exempt(self, entra_configured_default_secret_key_client):
        resp = entra_configured_default_secret_key_client.get("/api/health/live")
        assert resp.status_code == 200

    def test_forged_session_cookie_does_not_grant_access(
        self, entra_configured_default_secret_key_client,
    ):
        # The actual exploit this closes: sign a session with the
        # well-known default key and confirm it's still refused, because the
        # gate now blocks on secret_key_is_default() before ever consulting
        # is_authenticated().
        with entra_configured_default_secret_key_client.session_transaction() as sess:
            sess["authenticated"] = True
            sess["username"] = "forged-admin"
        resp = entra_configured_default_secret_key_client.get("/api/dob-repair/status")
        assert resp.status_code == 503


class TestLoginEntraRoute:
    def test_redirects_to_microsoft(self, entra_and_local_client, monkeypatch):
        fake = FakeMsalApp(auth_url="https://login.microsoftonline.com/fake?mock=1")
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        resp = entra_and_local_client.get("/login/entra")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "https://login.microsoftonline.com/fake?mock=1"

    def test_stashes_state_nonce_and_next_in_session(self, entra_and_local_client, monkeypatch):
        fake = FakeMsalApp()
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        entra_and_local_client.get("/login/entra?next=/dob-repair")
        with entra_and_local_client.session_transaction() as sess:
            assert sess["entra_state"]
            assert sess["entra_nonce"]
            assert sess["entra_next"] == "/dob-repair"

    def test_next_param_open_redirect_rejected_at_stash_time(self, entra_and_local_client, monkeypatch):
        fake = FakeMsalApp()
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        entra_and_local_client.get("/login/entra?next=http://evil.example.com/steal")
        with entra_and_local_client.session_transaction() as sess:
            assert sess["entra_next"] == "/"

    def test_redirects_to_local_login_when_entra_not_configured(self, configured_client):
        resp = configured_client.get("/login/entra")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_network_error_building_auth_url_falls_back_to_local_login_not_500(
        self, entra_and_local_client, monkeypatch,
    ):
        def _raise(*a, **k):
            raise RuntimeError("tenant discovery failed")
        monkeypatch.setattr("app.routes.auth.build_msal_app", _raise)

        resp = entra_and_local_client.get("/login/entra")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")


class TestAuthCallbackRoute:
    def test_idp_error_param_redirects_to_local_login(self, entra_and_local_client):
        resp = entra_and_local_client.get("/api/v1/auth/callback?error=access_denied")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_state_mismatch_rejected(self, entra_and_local_client):
        _stash_entra_session(entra_and_local_client, state="expected-state")
        resp = entra_and_local_client.get("/api/v1/auth/callback?state=wrong-state&code=abc")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_missing_state_in_session_rejected(self, entra_and_local_client):
        # No /login/entra call happened first — nothing was ever stashed.
        resp = entra_and_local_client.get("/api/v1/auth/callback?state=whatever&code=abc")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_missing_code_rejected(self, entra_and_local_client):
        _stash_entra_session(entra_and_local_client)
        resp = entra_and_local_client.get("/api/v1/auth/callback?state=expected-state")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_token_exchange_exception_falls_back_to_local_login_not_500(
        self, entra_and_local_client, monkeypatch,
    ):
        _stash_entra_session(entra_and_local_client)

        def _raise(*a, **k):
            raise RuntimeError("network blip")
        fake = FakeMsalApp()
        fake.acquire_token_by_authorization_code = _raise
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        resp = entra_and_local_client.get("/api/v1/auth/callback?state=expected-state&code=abc")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_token_exchange_error_result_rejected(self, entra_and_local_client, monkeypatch):
        _stash_entra_session(entra_and_local_client)
        fake = FakeMsalApp(token_result={"error": "invalid_grant", "error_description": "bad code"})
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        resp = entra_and_local_client.get("/api/v1/auth/callback?state=expected-state&code=abc")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_nonce_mismatch_rejected(self, entra_and_local_client, monkeypatch):
        _stash_entra_session(entra_and_local_client, nonce="expected-nonce")
        fake = FakeMsalApp(token_result={
            "id_token_claims": {"email": "person@doane.edu", "nonce": "wrong-nonce"},
        })
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        resp = entra_and_local_client.get("/api/v1/auth/callback?state=expected-state&code=abc")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        with entra_and_local_client.session_transaction() as sess:
            assert "authenticated" not in sess

    def test_missing_email_claim_rejected(self, entra_and_local_client, monkeypatch):
        _stash_entra_session(entra_and_local_client)
        fake = FakeMsalApp(token_result={
            "id_token_claims": {"nonce": "expected-nonce"},  # no email/preferred_username/upn
        })
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        resp = entra_and_local_client.get("/api/v1/auth/callback?state=expected-state&code=abc")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_successful_callback_logs_in(self, entra_and_local_client, monkeypatch):
        _stash_entra_session(entra_and_local_client)
        fake = FakeMsalApp(token_result={"id_token_claims": {
            "email": "person@doane.edu", "nonce": "expected-nonce",
        }})
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        resp = entra_and_local_client.get("/api/v1/auth/callback?state=expected-state&code=abc")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/")
        with entra_and_local_client.session_transaction() as sess:
            assert sess["authenticated"] is True
            assert sess["username"] == "person@doane.edu"

    def test_successful_callback_honors_next_path(self, entra_and_local_client, monkeypatch):
        _stash_entra_session(entra_and_local_client, next_path="/dob-repair")
        fake = FakeMsalApp(token_result={"id_token_claims": {
            "email": "person@doane.edu", "nonce": "expected-nonce",
        }})
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        resp = entra_and_local_client.get("/api/v1/auth/callback?state=expected-state&code=abc")
        assert resp.headers["Location"].endswith("/dob-repair")

    def test_claims_fallback_to_preferred_username_when_no_email(self, entra_and_local_client, monkeypatch):
        _stash_entra_session(entra_and_local_client)
        fake = FakeMsalApp(token_result={"id_token_claims": {
            "preferred_username": "person@doane.edu", "nonce": "expected-nonce",
        }})
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        entra_and_local_client.get("/api/v1/auth/callback?state=expected-state&code=abc")
        with entra_and_local_client.session_transaction() as sess:
            assert sess["username"] == "person@doane.edu"

    def test_claims_fallback_to_upn_when_no_email_or_preferred_username(self, entra_and_local_client, monkeypatch):
        _stash_entra_session(entra_and_local_client)
        fake = FakeMsalApp(token_result={"id_token_claims": {
            "upn": "person@doane.edu", "nonce": "expected-nonce",
        }})
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        entra_and_local_client.get("/api/v1/auth/callback?state=expected-state&code=abc")
        with entra_and_local_client.session_transaction() as sess:
            assert sess["username"] == "person@doane.edu"

    def test_successful_login_unlocks_gated_routes(self, entra_and_local_client, monkeypatch):
        _stash_entra_session(entra_and_local_client)
        fake = FakeMsalApp(token_result={"id_token_claims": {
            "email": "person@doane.edu", "nonce": "expected-nonce",
        }})
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)

        entra_and_local_client.get("/api/v1/auth/callback?state=expected-state&code=abc")
        assert entra_and_local_client.get("/api/dob-repair/status").status_code == 200


class TestEntraAuditAttribution:
    # The gate-level g.current_user wiring itself (i.e. that write_event()
    # picks up g.current_user when set) is unit-tested directly in
    # test_audit.py — decoupled from a real HTTP round trip so it isn't
    # sensitive to running many independent non-TESTING Flask app instances
    # (this file's _make_app() pattern) in the same test process. What's
    # specific to Entra and worth checking here is just that a successful
    # login results in the real email landing in the session, which the
    # gate then copies into g.current_user on every subsequent request.
    def test_successful_login_stores_real_identity_not_a_shared_string(self, entra_and_local_client, monkeypatch):
        _stash_entra_session(entra_and_local_client)
        fake = FakeMsalApp(token_result={"id_token_claims": {
            "email": "person@doane.edu", "nonce": "expected-nonce",
        }})
        monkeypatch.setattr("app.routes.auth.build_msal_app", lambda *a, **k: fake)
        entra_and_local_client.get("/api/v1/auth/callback?state=expected-state&code=abc")

        with entra_and_local_client.session_transaction() as sess:
            assert sess["username"] == "person@doane.edu"
            assert sess["username"] != "admin"  # not the shared local-login string
